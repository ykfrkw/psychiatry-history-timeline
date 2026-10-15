# 精神医学の歴史（見開き年表）

古代から現在までの精神医学の歴史を、松岡正剛『情報の歴史』風の縦組み見開き（A3 横 1 枚、または A4 縦 2 枚）にまとめた年表です。
右端の列は空欄で、印刷して医局・病院・学会などの沿革を書き込めます。

- 公開サイト: https://ykfrkw.github.io/psychiatry-history-timeline/
- 作成: 古川由己（精神科医）
- ライセンス: CC BY 4.0（`LICENSE.txt`）

## ダウンロードと印刷

| ファイル | 使い方 |
|---|---|
| [`docs/psychiatry-history-timeline_A3.pdf`](docs/psychiatry-history-timeline_A3.pdf) | A3 横で印刷（拡大縮小なし・実際のサイズ） |
| [`docs/psychiatry-history-timeline_A4x2.pdf`](docs/psychiatry-history-timeline_A4x2.pdf) | A4 縦で 2 枚印刷し、左右を貼り合わせて見開きに |
| [`docs/data/events.csv`](docs/data/events.csv) | 紙面に載っている項目のデータ（出典つき） |

公開サイトの HTML 版では、各項目にマウスを重ねると補足と出典が出ます。クリックすると Wikipedia・PubMed・Amazon（書籍）の検索リンクが出ます。

## 自分で作り直す

必要なもの: Python 3.11 以上（標準ライブラリのみ）、Google Chrome（PDF 化に使用）

```bash
python3 build.py profiles/public.toml --site docs/   # 公開版（このリポジトリの docs/ を作り直す）
python3 build.py profiles/sample_ikyoku.toml         # 医局版の例（ダミーデータ）
```

出力は `out/`（`timeline_<profile>_A3.pdf`、`_A4x2.pdf`、元の HTML）です。

### 項目を足す・直す

`data/events.csv` に 1 行足して、上のコマンドで作り直します。主な列は次のとおりです。

| 列 | 意味 |
|---|---|
| `year_start` / `year_end` / `year_label` | 年（紀元前は負の数）。期間なら終わりの年。表示用の年（空なら year_start） |
| `track` | 列。`world`（世界の制度・社会）/ `japan`（日本の制度・事件）/ `society`（日本の社会）/ `diagnosis`（疾患概念・診断）/ `mind`（精神病理・精神療法）/ `somatic`（身体療法・薬物） |
| `title` / `detail` | 見出し／補足（補足は強調項目では紙面に、それ以外はマウスを重ねたときに出ます） |
| `region` | 国名の略号（`独` `仏` `英` `米` `日` など） |
| `tags` | `;` 区切り（`exam` `drug` `sleep` `ethics` など）。`candidate`（掲載を検討中）と `unverified`（裏取りが済んでいない）は紙面に出しません |
| `importance` | 1（太字）/ 2 / 3 |
| `source` | 出典 |
| `emphasis` | `v`＝縦書きの帯 / `h`＝大きな見出し / `hl`＝横組みのハイライト / 空＝通常 |

項目をクリックしたときのリンク先（Wikipedia・Amazon・PubMed の検索語）は `data/links.csv` です。

### 医局版（右端の列を印字する版）を作る

1. `data/local_sample.csv` を複製して `data/local_<医局名>.csv` を作り、医局の沿革を書きます（列は events.csv と同じ）
2. 次のような `profiles/<医局名>.toml` を作ります

   ```toml
   extends = "base.toml"
   title = "精神医学の歴史 × ○○大学精神科"
   local_csv = "data/local_<医局名>.csv"
   local_heading = "○○大学精神科"
   ```

3. `python3 build.py profiles/<医局名>.toml`

列幅・文字の詰め方・列名などの共通設定は `profiles/base.toml` にあり、公開版も医局版もこれを土台にしています。
文字の大きさは、最も長い列が版面の下端に収まるよう、ブラウザでの実測をもとに自動で決まります（`timeline/fit.js`）。

## ライセンスとクレジット

この年表（PDF・HTML・データ）とコードは、クリエイティブ・コモンズ 表示 4.0 国際（CC BY 4.0）で提供します。改変・再配布・講義資料への利用ができます。

クレジット表記の例: 「精神医学の歴史」古川由己（精神科医）, CC BY 4.0, https://ykfrkw.github.io/psychiatry-history-timeline/

誤りに気づいた場合は、Issue か、ブログ（https://yukifurukawa.jp/）からお知らせください。
