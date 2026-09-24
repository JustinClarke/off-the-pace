import sys; sys.path.insert(0, "/Users/justin/github/off-the-pace")
import duckdb, pandas as pd
from ml.src import schema as S
c = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
cols = list(S.FEATURE_COLUMNS)
sel = ", ".join(f"avg(case when {x} is null then 1.0 else 0 end) as \"{x}\"" for x in cols)
df = c.sql(f"select race_year, count(*) n, {sel} from {S.MART} where is_training_eligible group by 1 order by 1").df()
pd.set_option("display.width", 250)
t = df.set_index("race_year").T
t.to_csv(sys.argv[1] if len(sys.argv)>1 else "/dev/null")
print(t.round(4).to_string())
# zero share too
sel0 = ", ".join(f"avg(case when try_cast({x} as double) = 0 then 1.0 else 0 end) as \"{x}\"" for x in cols if x not in S.CATEGORICAL_COLUMNS)
df0 = c.sql(f"select race_year, {sel0} from {S.MART} where is_training_eligible group by 1 order by 1").df()
print("\nZERO SHARE")
print(df0.set_index("race_year").T.round(4).to_string())
