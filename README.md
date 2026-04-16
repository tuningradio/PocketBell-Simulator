=================================
PocketBell Simulator Ver 1.0 by JA1XPM 2026/04/16
=================================

# PocketBell GUI

PocketBell GUI は、アマチュア無線の FM 音声回線上で DTMF を使って
ポケベル風のメッセージ送受信を行う GUI アプリケーションです。

## 特徴

- ポケベル風 GUI
- DTMF による送受信
- `*2*2` フリーワード本文対応
- `*4*4NN` 定型文本文対応
- 自局コールサイン設定
- 送受信履歴の保存とスクロール表示

## 必要環境

- Windows
- Python 3.10 系
- `requirements.txt` に記載のライブラリ
- オーディオ入出力環境
- PTT 制御用 COM ポート環境

## インストール

必要ライブラリを導入します。

```powershell
py -3.10 -m pip install -r requirements.txt
```

## 起動

`start_tx_gui.bat` を実行します。

起動前に `start_tx_gui.bat` の `OUTDEV` `INDEV` `COM` を環境に合わせて設定してください。

オーディオデバイス番号確認:

```powershell
py dtmftest_pager.py devices
```

## 入力例

```text
CQ,*2*2キンキュウ
JH1HUW,*4*402
```

## ドキュメント

- 詳しい使い方: `MANUAL.txt`
- 技術仕様: `SPEC.txt`

## ライセンス

本ソフトウェアは MIT License の条件で配布します。詳細は `LICENSE` を参照してください。
