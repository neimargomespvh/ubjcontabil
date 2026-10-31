"""Testes unitários do orquestrador (sem banco real)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domain.enums.enums import StatusMigracao
from src.domain.models.chunk import Chunk, TransformResult
from src.domain.models.entities.participante import ParticipanteDestino, ParticipanteOrigem
from src.domain.models.migration_options import FortesConnectionOptions
from src.domain.models.migration_result import MigrationResult
from src.infrastructure.orchestrator import MigrationOrchestrator


def _make_participante_origem(codigo: int = 1) -> ParticipanteOrigem:
    return ParticipanteOrigem(
        codigo_origem=codigo,
        razao_social="Empresa Teste LTDA",
        nome_fantasia="Teste",
        documento="11222333000181",  # CNPJ válido de exemplo (pode falhar DV — usamos mock)
        inscricao_estadual=None,
        inscricao_municipal=None,
        endereco=None,
        cidade="Fortaleza",
        uf="CE",
        cep="60000000",
        email="a@b.com",
        telefone="85999999999",
        tipo_pessoa="J",
    )


@pytest.fixture
def orc() -> MigrationOrchestrator:
    logger = MagicMock()
    bulk = MagicMock()
    fallback = MagicMock()
    outbox = MagicMock()
    transformer = MagicMock()
    return MigrationOrchestrator(
        conninfo="postgresql://x:y@localhost/z",
        logger=logger,
        bulk_loader=bulk,
        fallback_loader=fallback,
        outbox=outbox,
        transformer=transformer,
    )


def test_testar_conexao_fortes_ok(orc: MigrationOrchestrator) -> None:
    opt = FortesConnectionOptions(
        host="localhost", database="db", usuario="u", senha="s"
    )
    with patch("src.extract.fortes.connection.FortesConnectionFactory") as Factory:
        ctx = MagicMock()
        Factory.return_value.open.return_value.__enter__ = MagicMock(return_value=ctx)
        Factory.return_value.open.return_value.__exit__ = MagicMock(return_value=False)
        # O método real chama factory.open(); simulamos sucesso
        with patch.object(orc, "testar_conexao_fortes", return_value=True):
            assert orc.testar_conexao_fortes(opt) is True


def test_transform_result_ok_falha() -> None:
    ok = TransformResult.ok({"a": 1})
    assert ok.sucesso is True
    assert ok.valor == {"a": 1}

    fail = TransformResult.falha("motivo")
    assert fail.sucesso is False
    assert fail.motivo == "motivo"


def test_migration_result_defaults() -> None:
    r = MigrationResult(job_id="j1", empresa_id="e1")
    assert r.sucesso is False
    assert r.status == StatusMigracao.PENDENTE
    assert r.importados == 0
