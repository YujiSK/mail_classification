# PDF Renderer 動作確認

この文書は、移植したPDF生成モジュールの基本変換を確認するためのテストレポートです。

## 変換対象

Markdownから中間HTMLを生成し、そのHTMLをChromiumでPDFへ変換します。

| 項目 | 内容 | 状態 |
|---|---|---|
| 入力 | `outputs/test_report.md` | 準備済み |
| 中間生成物 | HTML・source registry | 自動生成 |
| 出力 | `outputs/test_report.pdf` | 検証対象 |

## 確認事項

見出し、本文、インラインコード、および表がPDFに含まれることを確認します。
