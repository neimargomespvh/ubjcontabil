"""Orquestrador: pipeline genérico (Empresa + Plano + Participante + SPED)."""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import psycopg

from src.domain.contracts.orchestrator import IMigrationOrchestrator
from src.domain.enums.enums import OperacaoSync, StatusMigracao
from src.domain.models.migration_options import FortesConnectionOptions
from src.domain.models.migration_progress import MigrationProgress
from src.domain.models.migration_result import MigrationResult
from src.extract.fortes.connection import FortesConnectionFactory
from src.extract.fortes.empresa_extractor import FortesEmpresaExtractor
from src.extract.fortes.participante_extractor import FortesParticipanteExtractor
from src.extract.fortes.plano_contas_extractor import FortesPlanoContasExtractor
from src.extract.tron.sped_txt_extractor import SpedTxtExtractor
from src.infrastructure.logging.migration_logger import MigrationLogger
from src.load.postgres_bulk_loader import PostgresBinaryBulkLoader
from src.load.postgres_fallback_loader import PostgresFallbackRowLoader
from src.load.sync_outbox_writer import SyncOutboxWriter
from src.transform.participante_transformer import ParticipanteTransformer
from src.extract.tron.sped_movimento_extractor import SpedMovimentoExtractor
from src.domain.models.entities.documento_fiscal import (
    DocumentoFiscal,
    ItemDocumentoFiscal,
)
from src.transform.sped.transformers import (
    SpedR0150ToParticipante,
    SpedR0500ToContaContabil,
)


@dataclass(slots=True)
class _Etapa:
    nome: str
    entidade: str
    extractor: Any
    transformer: Any | None
    loader: Callable[[psycopg.Connection, str, list[Any]], int]
    fallback: Callable[[psycopg.Connection, str, list[Any]], int]
    sync: bool = True
    id_fn: Callable[[Any], str] = field(default=lambda _: "")


def _id_codigo_origem(item: Any) -> str:
    return str(item.codigo_origem)


def _id_codigo(item: Any) -> str:
    return str(item.codigo)


class MigrationOrchestrator(IMigrationOrchestrator):
    def __init__(
        self,
        conninfo: str,
        logger: MigrationLogger,
        bulk_loader: PostgresBinaryBulkLoader,
        fallback_loader: PostgresFallbackRowLoader,
        outbox: SyncOutboxWriter,
        transformer: ParticipanteTransformer,
    ) -> None:
        self._conninfo = conninfo
        self._logger = logger
        self._bulk = bulk_loader
        self._fallback = fallback_loader
        self._outbox = outbox
        self._transformer = transformer

    # -- loaders/fetchers tipados (evitam lambdas longas) -------------
    def _load_empresas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_empresas(c, eid, itens)

    def _load_contas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_contas(c, eid, itens)

    def _load_participantes(
        self, c: psycopg.Connection, eid: str, itens: list[Any]
    ) -> int:
        return self._bulk.inserir_participantes(c, None, eid, itens)

    def _load_sped(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_sped(c, eid, itens)

    def _fb_empresas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._fallback.inserir_empresas(c, eid, itens)

    def _fb_contas(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._fallback.inserir_contas(c, eid, itens)

    def _fb_participantes(
        self, c: psycopg.Connection, eid: str, itens: list[Any]
    ) -> int:
        return self._fallback.inserir_participantes(c, None, eid, itens)

    def _fb_sped(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._fallback.inserir_sped(c, eid, itens)


    def _load_documentos(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_documentos(c, eid, itens)

    def _load_itens(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        return self._bulk.inserir_itens(c, eid, itens)

    def _load_movimentos(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        """Particiona chunk misto C100/C170 e grava nas tabelas corretas."""
        docs = [x for x in itens if isinstance(x, DocumentoFiscal)]
        items = [x for x in itens if isinstance(x, ItemDocumentoFiscal)]
        n = 0
        if docs:
            n += self._bulk.inserir_documentos(c, eid, docs)
        if items:
            n += self._bulk.inserir_itens(c, eid, items)
        return n

    def _fb_movimentos(self, c: psycopg.Connection, eid: str, itens: list[Any]) -> int:
        # Fallback simples: tenta bulk; em falha o orquestrador já trata
        return self._load_movimentos(c, eid, itens)

    # -- Fortes ------------------------------------------------------
    def testar_conexao_fortes(self, opt: FortesConnectionOptions) -> bool:
        try:
            with (
                FortesConnectionFactory(opt).open() as conn,
                conn.cursor() as cur,
            ):
                cur.execute("SELECT 1")
            return True
        except Exception as e:
            self._logger.erro("CONEXAO", "-", "Falha ao conectar na Fortes", e)
            return False

    def executar_migracao_fortes(
        self,
        opt: FortesConnectionOptions,
        progresso: Callable[[MigrationProgress], None],
        etapas: Sequence[str] = ("empresa", "plano_contas", "participante"),
    ) -> MigrationResult:
        factory = FortesConnectionFactory(opt)
        configs = self._config_etapas_fortes(factory, opt, etapas)
        return self._executar(
            tipo="FORTES", empresa_id=opt.empresa_id or opt.database,
            etapas=configs, progresso=progresso,
        )

    # -- Arquivos (SPED auditoria) -----------------------------------
    def executar_migracao_arquivos(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        etapas = [
            _Etapa(
                nome=f"sped:{Path(c).name}",
                entidade="sped_registro",
                extractor=SpedTxtExtractor(Path(c)),
                transformer=None,
                loader=self._load_sped,
                fallback=self._fb_sped,
                sync=False,
            )
            for c in caminhos
        ]
        return self._executar("SPED", empresa_id, etapas, progresso)

    # -- Arquivos (SPED estruturado) ---------------------------------
    def executar_migracao_sped_estruturada(
        self,
        caminhos: list[str],
        empresa_id: str,
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        """Pipeline estruturado: 0150 (participante) + 0500 (plano) + C100/C170 (movimento)."""
        etapas: list[_Etapa] = []
        for c in caminhos:
            p = Path(c)
            # Cadastros
            etapas.append(_Etapa(
                nome=f"sped-0150:{p.name}",
                entidade="participante",
                extractor=SpedTxtExtractor(p, registros=frozenset({"0150"})),
                transformer=SpedR0150ToParticipante(),
                loader=self._load_participantes,
                fallback=self._fb_participantes,
                id_fn=_id_codigo_origem,
            ))
            etapas.append(_Etapa(
                nome=f"sped-0500:{p.name}",
                entidade="conta_contabil",
                extractor=SpedTxtExtractor(p, registros=frozenset({"0500"})),
                transformer=SpedR0500ToContaContabil(),
                loader=self._load_contas,
                fallback=self._fb_contas,
                id_fn=_id_codigo,
            ))
            # Movimentos (C100 + C170 com vínculo documento→itens)
            etapas.append(_Etapa(
                nome=f"sped-movimento:{p.name}",
                entidade="documento_fiscal",
                extractor=SpedMovimentoExtractor(p),
                transformer=None,  # já transformado no extractor
                loader=self._load_movimentos,
                fallback=self._fb_movimentos,
                id_fn=lambda x: getattr(x, "codigo_origem", ""),
                sync=True,
            ))
        return self._executar("SPED-ESTRUTURADO", empresa_id, etapas, progresso)

    # -- pipeline genérico -------------------------------------------
    def _executar(
        self,
        tipo: str,
        empresa_id: str,
        etapas: list[_Etapa],
        progresso: Callable[[MigrationProgress], None],
    ) -> MigrationResult:
        job_id = str(uuid.uuid4())
        result = MigrationResult(job_id=job_id, empresa_id=empresa_id)
        inicio = time.time()
        self._logger.iniciar_job(job_id, tipo)
        progresso(MigrationProgress(etapa_atual=f"Conectando ({tipo})…"))

        try:
            with psycopg.connect(self._conninfo) as erp_conn:
                for etapa in etapas:
                    self._rodar_etapa(erp_conn, empresa_id, etapa, result, progresso)
            result.sucesso = True
            result.status = StatusMigracao.CONCLUIDO
            progresso(MigrationProgress(etapa_atual="Concluído", percentual=100.0))
        except Exception as e:
            result.status = StatusMigracao.FALHOU
            self._logger.erro("MIGRACAO", job_id, "Falha fatal", e)
            raise
        finally:
            result.duracao_segundos = time.time() - inicio
            self._logger.finalizar_job(job_id, result)
        return result

    def _rodar_etapa(
        self, erp_conn: psycopg.Connection, empresa_id: str,
        etapa: _Etapa, result: MigrationResult,
        progresso: Callable[[MigrationProgress], None],
    ) -> None:
        total_hint = self._total_hint(etapa.extractor)
        for chunk in self._iterar(etapa.extractor):
            validos = self._transformar(etapa, chunk.itens, result)
            if validos:
                with erp_conn.transaction():
                    try:
                        n = etapa.loader(erp_conn, empresa_id, validos)
                    except psycopg.Error as e_bulk:
                        self._logger.erro(
                            "BULK", etapa.nome,
                            f"COPY falhou ({e_bulk!s}); acionando fallback", e_bulk,
                        )
                        n = etapa.fallback(erp_conn, empresa_id, validos)
                    if etapa.sync and etapa.entidade:
                        ids = [etapa.id_fn(v) for v in validos]
                        self._outbox.enfileirar_batch(
                            erp_conn, empresa_id, etapa.entidade, ids,
                            OperacaoSync.UPSERT,
                        )
                    result.importados += n
            progresso(self._progresso(chunk, total_hint, etapa, result))

    @staticmethod
    def _total_hint(extractor: Any) -> int | None:
        if not callable(getattr(extractor, "count_estimado", None)):
            return None
        try:
            valor = extractor.count_estimado()
        except Exception:
            return None
        return cast(int | None, valor)

    @staticmethod
    def _iterar(extractor: Any) -> Iterable[Any]:
        return cast(Iterable[Any], extractor.extract())

    def _transformar(
        self, etapa: _Etapa, itens: list[Any], result: MigrationResult
    ) -> list[Any]:
        if etapa.transformer is None:
            return list(itens)
        validos: list[Any] = []
        for item in itens:
            t = etapa.transformer.transform(item)
            if t.sucesso and t.valor is not None:
                validos.append(t.valor)
            else:
                result.erros += 1
                rid = etapa.id_fn(item) or getattr(item, "codigo_origem", "?")
                self._logger.erro(etapa.entidade, str(rid), t.motivo or "?")
        return validos

    @staticmethod
    def _progresso(
        chunk: Any, total_hint: int | None, etapa: _Etapa, result: MigrationResult,
    ) -> MigrationProgress:
        pct = 0.0
        if total_hint:
            pct = min(99.0, 100.0 * chunk.total_acumulado / total_hint)
        return MigrationProgress(
            etapa_atual=f"Importando {etapa.nome}…",
            registros_processados=chunk.total_acumulado,
            registros_com_erro=result.erros,
            percentual=pct,
        )

    # -- config Fortes -----------------------------------------------
    def _config_etapas_fortes(
        self, factory: FortesConnectionFactory,
        opt: FortesConnectionOptions, etapas: Sequence[str],
    ) -> list[_Etapa]:
        mapa: dict[str, _Etapa] = {
            "empresa": _Etapa(
                nome="empresa", entidade="empresa",
                extractor=FortesEmpresaExtractor(factory, opt.tamanho_chunk),
                transformer=None,
                loader=self._load_empresas,
                fallback=self._fb_empresas,
                id_fn=_id_codigo_origem,
            ),
            "plano_contas": _Etapa(
                nome="plano_contas", entidade="conta_contabil",
                extractor=FortesPlanoContasExtractor(factory, opt.tamanho_chunk),
                transformer=None,
                loader=self._load_contas,
                fallback=self._fb_contas,
                id_fn=_id_codigo,
            ),
            "participante": _Etapa(
                nome="participante", entidade="participante",
                extractor=FortesParticipanteExtractor(factory, opt.tamanho_chunk),
                transformer=self._transformer,
                loader=self._load_participantes,
                fallback=self._fb_participantes,
                id_fn=_id_codigo_origem,
            ),
        }
        faltando = [n for n in etapas if n not in mapa]
        if faltando:
            raise ValueError(f"Etapas desconhecidas: {faltando}")
        return [mapa[n] for n in etapas]
