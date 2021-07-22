import numpy as np
import pandas as pd
import pywebio
from pywebio.input import select, checkbox, radio, textarea, input_group
from pywebio.output import put_table
from ortools.sat.python import cp_model

##### Web画面からの入力 ######

result = input_group(
  "入力グループ",
  [
    textarea('日付 FROM', rows=1, placeholder='yyyy/mm/dd', name="from"), # 日付 ～から
    textarea('日付 TO', rows=1, placeholder='yyyy/mm/dd', name="to"), # 日付 ～まで

    checkbox("メニュー",  # メニュー
            options=['カレー', 'ラーメン', '焼きそば'],
             name="menu"),

    checkbox("曜日",  # スケジュールをたてる曜日
            options=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
             name="dayOfWeek"),
  ]
)

######## 最適化処理 #########

# 日付マスター
time_range_list = pd.date_range(start=result["from"], end=result["to"])
  

days_df = pd.DataFrame(
    [
      [*range(len(time_range_list))], # index 
      [*time_range_list] # 選択した日付のFROMからTOまで
    ],
).T
days_df.columns = ["id", "Days"]
days_df["Days"] = pd.to_datetime(days_df["Days"], format='%Y%m%d') # 時間が表示されないよう修正
days_df["DayOfTheWeek"] = days_df["Days"].dt.strftime('%a') # 曜日を取得
days_df["Days"] = days_df["Days"].astype(str) # 表に年月日だけ表示されるように文字列に変換
days_df[days_df["DayOfTheWeek"].isin(result["dayOfWeek"])].reset_index(drop=True) # 曜日の絞り込み

# メニューマスター
menue_df = pd.DataFrame(
    [
        [*range(len(result["menu"]))], # index
        result["menu"] # 選択したメニューのリスト
    ],
).T
menue_df.columns = ["id", "Food"]


# 食事時マスター
shift_df = pd.DataFrame(
    [
        [0],
        ["昼"]
    ],
).T
shift_df.columns = ["id", "Shift"]

# パラメーター
num_menues = len(menue_df) # メニューの数
num_shifts = len(shift_df) # 食事時の数
num_days = len(days_df) # 日付の数
all_menues = range(num_menues)
all_shifts = range(num_shifts)
all_days = range(num_days)


### ランダムベースの食事表の作成
# とりあえず必要数だけ 0 で埋める
schedule_list = np.zeros((num_menues, num_days, num_shifts))

# シフトの1つのindexを指定。これを 1 に変換して、シフトのうち1つだけ 1になっている3次元のリストを作成
order_num = np.random.randint(0,num_shifts,(num_menues, num_days))

for i in range(len(schedule_list)):
    for j in range(len(schedule_list[i])):
        schedule_list[i][j][order_num[i][j]]=1
shift_requests = schedule_list.astype(np.int32).tolist()


# モデルの作成
model = cp_model.CpModel()


# 条件の反映
shifts = {}
for n in all_menues:
    for d in all_days:
        for s in all_shifts:
            shifts[(n, d,
                    s)] = model.NewBoolVar('shift_n%id%is%i' % (n, d, s))


# 割り当て
for d in all_days:
    for s in all_shifts:
        model.Add(sum(shifts[(n, d, s)] for n in all_menues) == 1)


# メニューは1日に最大1種類
for n in all_menues:
    for d in all_days:
        model.Add(sum(shifts[(n, d, s)] for s in all_shifts) <= 1)


# メニューは最低でも均等に登場
min_shifts_per_menue = (num_shifts * num_days) // num_menues
if num_shifts * num_days % num_menues == 0:
    max_shifts_per_menue = min_shifts_per_menue
else:
    max_shifts_per_menue = min_shifts_per_menue + 1
    
for n in all_menues:
    num_shifts_worked = 0
    for d in all_days:
        for s in all_shifts:
            num_shifts_worked += shifts[(n, d, s)]
    model.Add(min_shifts_per_menue <= num_shifts_worked)
    model.Add(num_shifts_worked <= max_shifts_per_menue)

# 目的変数の最小化
model.Maximize(
    sum(shift_requests[n][d][s] * shifts[(n, d, s)] for n in all_menues
        for d in all_days for s in all_shifts))


# 最適スケジュール結果を格納する辞書型
schedule_dict = {}

# ソルバーを呼び出して結果を取得
solver = cp_model.CpSolver()
solver.Solve(model)
for d in all_days:
    schedule_dict[d] = {}
    
    for n in all_menues:
        for s in all_shifts:
            if solver.Value(shifts[(n, d, s)]) == 1:
                if shift_requests[n][d][s] == 1:
                    schedule_dict[d][n] = {}
                    schedule_dict[d][n][s]  = "(希望通り)" 
                    
                else:
                    schedule_dict[d][n] = {}
                    schedule_dict[d][n][s]  = "(希望ではない)"


# Statistics.
print('  - Number of shift requests met = %i' % solver.ObjectiveValue(),
      '(out of', num_menues * min_shifts_per_menue, ')')
print('  - wall time       : %f s' % solver.WallTime())


# ### DataFrame化
# Day -> menue -> shift -> request の順
plan_df = pd.DataFrame()

for day in schedule_dict:
    for menue in schedule_dict[day]:
        for shift in schedule_dict[day][menue]:
            tmp_df = pd.DataFrame(
                [[
                    day, menue, shift, schedule_dict[day][menue][shift]
                ]],
                columns=["DaysId", "MenueId", "ShiftId", "Request"]
            )
            plan_df = pd.concat([plan_df, tmp_df])

plan_df = plan_df.sort_values(['DaysId', 'ShiftId'], ascending=[True, True])
plan_df = plan_df.reset_index(drop=True)

### 作成したDataFrameとマスターの統合
# 曜日
plan_df = pd.merge(plan_df, days_df, left_on="DaysId", right_on="id", how='left').drop(columns='id')

# メニュー
plan_df = pd.merge(plan_df, menue_df, left_on="MenueId", right_on="id", how='left').drop(columns='id')

# いつ食べるか（シフト）
plan_df = pd.merge(plan_df, shift_df, left_on="ShiftId", right_on="id", how='left').drop(columns='id')

plan_df = plan_df[["Days", "DayOfTheWeek", "Shift", "Food"]]
plan_df.columns = ["日付", "曜日", "いつ", "メニュー"]

##### Web画面へのアウトプット ######

put_table(
  plan_df.values.tolist(),
  header=plan_df.columns.tolist(),
)