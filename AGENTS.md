# AI editor rules for Task 10

- 開発開始前に `docs/management/project_rules.md` を読むこと。同ファイルを本プロジェクト規約の正本とする。
- 既存資産を再実装する前に `docs/audits/task10_reuse_matrix.md` を確認する。
- `Pipeline` 外で学習型前処理をfitしない。
- `raw_text`を上書きしない。
- 全条件・全モデルで同一の評価Foldを使用する。
- 統計的リークと、本文・メタデータ・templateによる内容リークを別々に検査する。
- Core実験完成前にExtensionへ進まない。
- 生成物を`src/`や`scripts/`へ保存しない。
- 実験結果をreportへ手動転記しない。
- 不明点を推測で実装せず、TODOまたは監査上の未確認事項として記録する。
- 課題10分類コード、合成data生成、学習・CVは、監査・設計の承認前に実装しない。
