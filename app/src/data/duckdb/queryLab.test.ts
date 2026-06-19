import { describe, it, expect } from 'vitest'
import { assertReadOnly, resolveTablesInSql, QueryLabError } from './queryLab'
import type { DataManifest } from '../manifest'

const manifest: DataManifest = {
  version: 'test',
  generatedAt: '2026-06-19',
  tables: [
    { name: 'dim_circuits', path: '/d/dim_circuits.parquet', partitioned: false },
    { name: 'fct_stint_features', path: '/d/fct_stint_features.parquet', partitioned: false },
    { name: 'race_to_track', path: '/d/race_to_track.parquet', partitioned: false },
    { name: 'mart_corner_skill_driver', path: '/d/mart_corner_skill_driver', partitioned: true },
  ],
}

describe('assertReadOnly', () => {
  const allow = [
    'SELECT * FROM dim_circuits',
    'select 1',
    'WITH t AS (SELECT 1) SELECT * FROM t',
    'EXPLAIN SELECT * FROM dim_circuits',
    'DESCRIBE dim_circuits',
    'SUMMARIZE dim_circuits',
    'SHOW TABLES',
    'PRAGMA table_info(dim_circuits)',
    'SELECT * FROM dim_circuits;', // single trailing semicolon ok
    '-- comment\nSELECT 1',
  ]
  it.each(allow)('allows %s', sql => {
    expect(() => assertReadOnly(sql)).not.toThrow()
  })

  const deny = [
    'DROP VIEW dim_circuits',
    'CREATE TABLE x AS SELECT 1',
    'ALTER TABLE x ADD COLUMN y INT',
    'INSERT INTO x VALUES (1)',
    'UPDATE x SET y = 1',
    'DELETE FROM x',
    'ATTACH \'foo.db\'',
    'COPY x TO \'out.csv\'',
    'INSTALL httpfs',
    'LOAD httpfs',
    'PRAGMA database_list',
    'SET threads = 4',
    'SELECT 1; DROP VIEW dim_circuits', // multi-statement
    '',
    '   ',
  ]
  it.each(deny)('rejects %s', sql => {
    expect(() => assertReadOnly(sql)).toThrow(QueryLabError)
  })
})

describe('resolveTablesInSql', () => {
  it('extracts referenced manifest tables', () => {
    const sql = 'SELECT * FROM fct_stint_features WHERE compound IS NOT NULL'
    expect(resolveTablesInSql(sql, manifest)).toEqual(['fct_stint_features'])
  })

  it('matches literal-named tables and joins', () => {
    const sql = 'SELECT * FROM dim_circuits c JOIN race_to_track r ON c.id = r.id'
    expect(resolveTablesInSql(sql, manifest).sort()).toEqual(['dim_circuits', 'race_to_track'])
  })

  it('matches partitioned tables', () => {
    expect(resolveTablesInSql('SELECT * FROM mart_corner_skill_driver', manifest)).toEqual(['mart_corner_skill_driver'])
  })

  it('ignores tables not referenced', () => {
    expect(resolveTablesInSql('SELECT 1', manifest)).toEqual([])
  })

  it('does not match substrings of other identifiers', () => {
    // a column aliased similarly should not register a table
    const sql = 'SELECT 1 AS dim_circuits_count'
    expect(resolveTablesInSql(sql, manifest)).toEqual([])
  })

  it('ignores table names inside comments', () => {
    const sql = '-- old: SELECT * FROM fct_stint_features\nSELECT * FROM dim_circuits'
    expect(resolveTablesInSql(sql, manifest)).toEqual(['dim_circuits'])
  })
})
