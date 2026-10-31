"""ERP Contábil — Módulo de Migração.

Este pacote reúne os 4 motores de ETL (Extract, Transform, Load) e a
infraestrutura de orquestração para migrar dados de sistemas concorrentes
(Fortes Tecnologia / Tron Informática / SPED) para o banco local PostgreSQL.

Camadas:
    domain          → contratos, modelos e enums (sem dependências externas)
    extract         → conexão e leitura das bases de origem
    transform       → De-Para, validações contábeis e normalizações
    load            → inserção em alta performance + outbox do sincronizador delta
    infrastructure  → logger, retry, telemetria e orquestrador
    web             → painel do administrador
"""
