# Agree Game

一個前台 + 後台的小型投票遊戲，固定只有一題。

## 檔案角色

- `game.html`：遊戲頁
- `admin.html`：後台頁
- `server.py`：Python 後端，負責投票、登入和統計
- `assets/`：共用 CSS / JS
- `data/questions.json`：固定題目資料
- `data/agree_votes.sqlite3`：自動建立的投票資料庫
- `render.yaml`：Render 部署設定

## 執行方式

```powershell
cd C:\Users\88692\Documents\agree_game
py server.py
```

開啟：

- 遊戲頁：`http://127.0.0.1:5000/`
- 後台：`http://127.0.0.1:5000/admin`

預設後台密碼是 `admin`。如果你要改成別的，啟動前設定 `ADMIN_PASSWORD` 就會覆蓋預設值。

後台登入後可以：

- 修改密碼
- 清空投票紀錄
- 查看每題統計和最近回應

## 重置資料

如果你想清空投票紀錄，可以直接在後台按「清空紀錄」。
如果你想整個重建資料庫，刪掉 `data/agree_votes.sqlite3` 也可以，下一次啟動會自動重建。

## GitHub 部署

這個專案不是純靜態頁面，所以 **GitHub Pages 不夠**，因為它不能跑 `server.py`。

比較簡單的做法是：

1. 把整個專案推到 GitHub
2. 在 Render 建一個 Web Service，直接連你的 GitHub repository
3. Render 會替你跑 `python server.py`，然後給你一個公開網址

`render.yaml` 已經幫你放好基本設定。你只要在 Render 上建立服務，並設定：

- `SECRET_KEY`
- `ADMIN_PASSWORD`，如果你想改預設密碼

如果你之後有清空紀錄，前台會自動恢復可投票，不需要叫使用者清瀏覽器資料。
