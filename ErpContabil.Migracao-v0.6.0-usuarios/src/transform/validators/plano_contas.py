"""Validação contábil do plano de contas."""
from __future__ import annotations

from src.domain.models.chunk import ResultadoValidacaoPlano
from src.domain.models.entities.conta_contabil import ContaContabil


class PlanoContasValidator:
    """Regras mínimas de consistência do plano de contas.

    Regras (portadas do C#):
        1. Sintética DEVE ter ao menos um filho.
        2. Analítica NÃO pode ter filhos (é onde os lançamentos batem).
        3. Todo codigo_pai deve existir na lista.
        4. Não pode haver ciclo (A→B→A).
        5. Grau do filho = grau do pai + 1.
        6. Natureza de saldo obrigatória na analítica.
    """

    @staticmethod
    def validar(contas: list[ContaContabil]) -> ResultadoValidacaoPlano:
        """Verifica sintéticas/analíticas, pai existente, ciclo, grau e natureza de saldo."""
        erros: list[str] = []
        if not contas:
            return ResultadoValidacaoPlano(valido=False, erros=["Plano de contas vazio."])

        por_codigo: dict[str, ContaContabil] = {c.codigo: c for c in contas}

        # índice de filhos (para checar se sintética/analítica está no nível certo)
        filhos: dict[str, list[ContaContabil]] = {}
        for c in contas:
            if c.codigo_pai is not None:
                filhos.setdefault(c.codigo_pai, []).append(c)

        # checagens linha-a-linha
        for conta in contas:
            if conta.codigo_pai is not None:
                pai = por_codigo.get(conta.codigo_pai)
                if pai is None:
                    erros.append(
                        f"Conta {conta.codigo}: pai '{conta.codigo_pai}' inexistente."
                    )
                elif conta.grau != pai.grau + 1:
                    erros.append(
                        f"Conta {conta.codigo}: grau {conta.grau} != "
                        f"grau do pai ({pai.grau}) + 1."
                    )

            tem_filhos = conta.codigo in filhos and len(filhos[conta.codigo]) > 0

            if conta.natureza == "SINTETICA" and not tem_filhos:
                erros.append(
                    f"Conta sintética {conta.codigo} não possui contas filhas."
                )

            if conta.natureza == "ANALITICA":
                if tem_filhos:
                    erros.append(
                        f"Conta analítica {conta.codigo} possui filhas — "
                        f"deve ser sintética."
                    )
                if not conta.natureza_saldo or not conta.natureza_saldo.strip():
                    erros.append(
                        f"Conta analítica {conta.codigo} sem natureza de saldo (D/C)."
                    )

            if conta.natureza not in ("SINTETICA", "ANALITICA"):
                erros.append(
                    f"Conta {conta.codigo}: natureza '{conta.natureza}' inválida."
                )

        # detecção de ciclo
        for conta in contas:
            visitados: set[str] = set()
            atual = conta
            while (
                atual.codigo_pai is not None
                and atual.codigo_pai in por_codigo
            ):
                if atual.codigo in visitados:
                    erros.append(
                        f"Ciclo detectado no plano de contas a partir de {conta.codigo}."
                    )
                    break
                visitados.add(atual.codigo)
                atual = por_codigo[atual.codigo_pai]

        return ResultadoValidacaoPlano(valido=not erros, erros=erros)
