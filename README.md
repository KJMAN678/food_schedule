### food_schedule

- [数理最適化によってこち亀の両さんのお昼の食事メニューを決めてあげるアプリ](https://food-schedule.herokuapp.com/)

[アプリ概要](https://crieit.net/boards/web1week-202107/92ddbbc42e78fd9a710a58f219e837fd)

いつからいつまでなのか、対象とする年月日をテキストエリアに入力し、メニュー（カレー、ラーメン、焼きそば）と対象とする曜日を選んであげよう！  

ただでさえ少ないバリエーション（カレー、ラーメン、焼きそば）をさらに狭めることも可能！  

<img width="682" alt="2021-07-23_11h12_12" src="https://user-images.githubusercontent.com/45703844/126730081-999de7de-b0b3-454f-a521-3ee5102ac3a9.png">

重複しないように、偏らないように数理最適化を無駄遣いするぞ！  

<img width="355" alt="2021-07-23_11h11_48" src="https://user-images.githubusercontent.com/45703844/126730133-fc4a8ce6-7910-4b6d-915f-3c569b67acb4.png">

* 両さんの昼食はカレー、ラーメン、ヤキソバの繰り返し
 こちら葛飾区亀有公園前派出所 第84巻の第2話「現代昼食事情の巻」より  
 https://igmonostone.com/kochikame-84_lifehack/
 
数理最適化には or-tools を使っています  
https://developers.google.com/optimization

Webアプリ作成には PyWebIO と一部 Flask を使っています  
https://pywebio.readthedocs.io/en/latest/index.html

デプロイ周りについては下記のYouTube、GitHubを参考にしました  
https://www.youtube.com/watch?v=sqR154NkwZk  
https://github.com/krishnaik06/Pywebheroku  
