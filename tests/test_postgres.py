import os
import uuid

import pytest


def test_fresh_postgres_and_replacement_import(tmp_path):
    url = os.getenv('TEST_POSTGRES_ADMIN_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_ADMIN_URL 미설정')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from needs_agent.postgres import PostgresRepository
    from needs_agent import NeedsFoodRepository
    from scripts.migrate_sqlite_to_postgres import migrate
    name = 'needs_test_' + uuid.uuid4().hex[:12]
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            options = conninfo_to_dict(url)
            options['dbname'] = name
            target_url = make_conninfo(**options)
            with psycopg.connect(target_url) as fresh:
                assert fresh.execute("SELECT 1 FROM pg_type WHERE typname='vector'").fetchone() is None
            repo = PostgresRepository(target_url)
            assert repo.dashboard()['planned_meals'] == 6800
            assert repo.recipe_cost('닭갈비')
            repo.set_setting('test_setting', 'saved')
            assert PostgresRepository(target_url).get_setting('test_setting') == 'saved'
            with repo._connect() as con:
                assert con.execute("SELECT 1 FROM pg_indexes WHERE indexname='knowledge_embedding_hnsw'").fetchone()
            vector = [0.01] * 1536
            repo.save_embedding('NF-KB-009', vector)
            assert repo.nearest_knowledge(vector)[0]['document_id'] == 'NF-KB-009'
            path = tmp_path/'source.db'
            source = NeedsFoodRepository(path)
            source.set_setting('test_setting', 'migrated')
            first = migrate(path, repo)
            assert migrate(path, repo) == first
            assert repo.get_setting('test_setting') == 'migrated'
            assert repo.browse_table('recipe_costs')['total'] == 5
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
