# 精神医学の歴史（年表）

最新版: https://ykfrkw.github.io/psychiatry-history-timeline/　／　最終更新: 2026-10-15

## 使い方

- `psychiatry-history-timeline_A3.pdf` を A3 横で印刷します（拡大縮小なし・「実際のサイズ」で）
- A3 が無ければ `psychiatry-history-timeline_A4x2.pdf` を A4 縦で 2 枚印刷し、左右を貼り合わせて見開きにします
- 右端の空欄の列には、医局・病院・学会などの沿革を手書きで書き込めます（見出しも空欄です）。
  破線と小さな年（1900・1945・1995）は、左の列とおおよそ同じ高さの目安です
- `index.html` をブラウザで開くと、画面で拡大して読めます。各項目にマウスを重ねると補足と出典が出ます
- `data/events.csv` は紙面に載っている項目だけのデータです（列の意味は GitHub リポジトリの README を参照）

## 医局版（空欄の列を印字する版）の作り方

GitHub リポジトリの README「医局版の作り方」の手順に従い、医局の沿革を CSV に書いて
`python3 build.py profiles/<医局名>.toml` で作ります。

## ライセンス

CC BY 4.0（`LICENSE.txt`）。クレジット表記の例: 「精神医学の歴史」古川由己（精神科医）, CC BY 4.0, https://ykfrkw.github.io/psychiatry-history-timeline/
