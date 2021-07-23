import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
import pywebio
from pywebio.input import select, checkbox, textarea, input_group
from pywebio.output import put_table, put_text, put_scrollable, output
from ortools.sat.python import cp_model

from pywebio.platform.flask import webio_view
from pywebio import STATIC_PATH
import argparse
from pywebio import start_server

from flask import Flask, send_from_directory

app = Flask(__name__)

def make_schedule():

  ##### Web画面からの入力 ######

  today = datetime.today() # 今日の日付
  seven_days_later = today + timedelta(days=7) # 7日後

  result = input_group(
    "こち亀の両さんの昼食のローテーションを決めてあげるアプリ",
    [
      textarea('日付 FROM', # 日付 ～から 
            rows=1,
            value=datetime.strftime(today, '%Y-%m-%d'),  # 今日の日付(サンプル)
            placeholder='yyyy/mm/dd', 
            name="from"),

      textarea('日付 TO', # 日付 ～まで 
            rows=1, 
            value=datetime.strftime(seven_days_later, '%Y-%m-%d'), # 7日後の日付(サンプル)
            placeholder='yyyy/mm/dd', 
            name="to"),

      checkbox("メニュー",  # メニュー
              options=['カレー', 'ラーメン', '焼きそば'],
              value=['カレー', 'ラーメン', '焼きそば'],
              name="menu"),

      checkbox("曜日",  # スケジュールをたてる曜日
              options=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
              value=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
              name="dayOfWeek"),
    ]
  )

  ######## 最適化処理 #########

  # 日付マスター
  time_range_list = pd.date_range(start=result["from"], end=result["to"])

  days_df = pd.DataFrame(
      [
        [*time_range_list] # 選択した日付のFROMからTOまで
      ],
  ).T
  days_df.columns = ["Days"]
  days_df["dayOfWeek"] = days_df["Days"].dt.strftime('%a') # 曜日を取得
  days_df["Days"] = days_df["Days"].astype(str) # 表に年月日だけ表示されるように文字列に変換
  days_df = days_df[days_df["dayOfWeek"].isin(result["dayOfWeek"])].reset_index(drop=True) # 曜日の絞り込み
  days_df = days_df[days_df["dayOfWeek"].isin(result["dayOfWeek"])].reset_index()
  days_df.columns = ["id", "Days", "dayOfWeek"]


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

  plan_df = plan_df[["Days", "dayOfWeek", "Shift", "Food"]]
  plan_df.columns = ["日付", "曜日", "いつ", "メニュー"]

  ##### Web画面へのアウトプット ######

  title = output(put_text("両さんの昼食ローテーション"))
  columns = output(put_table(np.array(plan_df.columns).reshape(1, -1).tolist()))
  tables = output(put_scrollable(put_table(plan_df.values.tolist()), height=300, keep_bottom=True))  # equal to output('Coding')

  # 食べたメニューの数
  count = plan_df["メニュー"].value_counts().reset_index()
  count.columns = ["メニュー", "数量"]
  count_table = put_table(count.values.tolist(), header=list(count.columns))

  put_table([
    [title],
    [columns],
    [tables],
    [count_table]
  ])

# app.add_url_rule('/schedule', 'webio_view', webio_view(make_schedule),
#             methods=['GET', 'POST', 'OPTIONS'])

# if __name__ == '__main__':
#     parser = argparse.ArgumentParser()
#     parser.add_argument("-p", "--port", type=int, default=8080)
#     args = parser.parse_args()

#     start_server(make_schedule, port=args.port)

if __name__ == '__main__':
    make_schedule()

app.run(host='localhost', port=80)

