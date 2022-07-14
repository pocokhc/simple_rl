

# v0.5.3

+ history作成
+ 複数プレイ時の1ターンで実行できるプレイヤー数を、複数人から一人固定に変更。
  + 実装を複雑にしているだけでメリットがほぼなさそうだったので
  + 1ターンに複数人実行したい場合も、環境側で複数ターンで各プレイヤーのアクションを収集すれば実現できるため
  + これに伴い EnvBase のIFを一部変更
+ MCTSを実装
  + 実装に伴い rl.algorithms.modelbase を追加
+ runner.renderの引数を一部変更
  + terminal,GUI,animationの描画をそれぞれ設定できるように変更
+ OXにGUIを実装
+ modelbaseのシミュレーションstep方法を修正(RL側メインに変更)