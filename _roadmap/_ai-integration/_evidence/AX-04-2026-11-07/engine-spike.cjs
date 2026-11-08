const path = require('path')
const APP = '/Users/justin/github/off-the-pace/app'
const { createDuckDB, NODE_RUNTIME, ConsoleLogger, DuckDBDataProtocol } = require(APP + '/node_modules/@duckdb/duckdb-wasm/dist/duckdb-node-blocking.cjs')
const DIST = APP + '/node_modules/@duckdb/duckdb-wasm/dist'
;(async () => {
  const t0 = Date.now()
  const db = await createDuckDB({ mvp: { mainModule: path.join(DIST, 'duckdb-mvp.wasm'), mainWorker: path.join(DIST, 'duckdb-node-mvp.worker.cjs') }, eh: { mainModule: path.join(DIST, 'duckdb-eh.wasm'), mainWorker: path.join(DIST, 'duckdb-node-eh.worker.cjs') } }, new ConsoleLogger(), NODE_RUNTIME)
  await db.instantiate()
  const f = process.argv[2]
  db.registerFileURL('t.parquet', f, DuckDBDataProtocol.NODE_FS, false)
  const c = db.connect()
  const r = c.query("SELECT COUNT(*) AS n FROM read_parquet('t.parquet')").toArray()
  console.log('rows', r[0].toJSON(), 'version', c.query('select version() v').toArray()[0].toJSON(), 'ms', Date.now() - t0)
})().catch(e => { console.error('FAIL', e); process.exit(1) })
