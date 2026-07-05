# Agree Game 部署指南

## 部署方案：前台 GitHub Pages + 後端 Render

這個指南將協助您將投票遊戲部署到線上，讓其他人可以透過網址訪問。

---

## 第一部分：部署後端到 Render

### 步驟 1：準備 GitHub Repository

1. 在 GitHub 上建立一個新的 repository（例如：`agree-game`）
2. 將整個 `agree_game` 資料夾的內容推送到這個 repository

### 步驟 2：在 Render 建立 Web Service

1. 前往 [Render](https://render.com/) 並註冊/登入帳號
2. 點擊 **"New +"** → **"Web Service"**
3. 連接您的 GitHub repository
4. 設定如下：
   - **Name**: `agree-game`（或您喜歡的名稱）
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python server.py`
   - **Plan**: 選擇免費方案（Free）

5. 在 **Environment Variables** 中設定：
   - `SECRET_KEY`: 設定一個隨機的金鑰（例如：`your-random-secret-key-12345`）
   - `ADMIN_PASSWORD`: 設定您的後台密碼（例如：`your-secure-password`）

6. 點擊 **"Create Web Service"**

### 步驟 3：取得後端網址

部署完成後，Render 會提供一個網址，例如：
```
https://agree-game.onrender.com
```

**請記下這個網址，後續步驟會用到。**

---

## 第二部分：部署前台到 GitHub Pages

### 步驟 1：建立前台專案

1. 在 GitHub 上建立一個新的 repository（例如：`agree-game-frontend`）
2. 在 repository 中建立以下檔案結構：

**方法 A：使用 GitHub 網頁介面**
- 點擊 "Add file" → "Create new file"
- 檔案路徑輸入：`game.html`
- 貼上 `game.html` 的內容
- 重複建立 `assets/game.js` 和 `assets/styles.css`

**方法 B：使用 Git 命令**
```bash
# 複製檔案到新資料夾
mkdir agree-game-frontend
cd agree-game-frontend
cp ../agree_game/game.html .
cp -r ../agree_game/assets .
```

3. 確認 repository 結構如下：
```
agree-game-frontend/
├── game.html
└── assets/
    ├── game.js
    └── styles.css
```

### 步驟 2：選擇正確的 game.js 版本

這個專案現在有三個 game.js 相關檔案，請按照以下說明使用：

**檔案對照表**：

| 檔案名稱 | API 網址類型 | 使用位置 | 說明 |
|---------|------------|---------|------|
| `game.js`（原本的） | 固定網址 | ⚠️ 不使用 | 這是開發過程中的版本，現在不需要使用 |
| `game.backend.js` | 動態網址 | 後端 Render | 使用 `window.location.origin`，自動適應 Render 網址 |
| `game.frontend.js` | 固定網址 | 前台 GitHub Pages | 固定指向 `https://the-plan.onrender.com` |

**後端 Repository（部署到 Render）的檔案選擇**：
```
agree-game/
├── server.py
├── render.yaml
├── data/
├── assets/
│   ├── game.backend.js  ← 使用這個（重新命名為 game.js）
│   ├── game.js          ← 原本的，可以刪除或忽略
│   └── styles.css
├── game.html
├── admin.html
└── requirements.txt
```

**操作**：
1. 將 `assets/game.backend.js` 重新命名為 `assets/game.js`
2. 可以刪除原本的 `assets/game.js`（或保留但不會被使用）
3. 推送到 GitHub，Render 會自動部署

**前台 Repository（部署到 GitHub Pages）的檔案選擇**：
```
agree-game-frontend/
├── game.html
└── assets/
    ├── game.js  ← 使用 game.frontend.js 重新命名
    └── styles.css
```

**操作**：
1. 將 `game.frontend.js` 重新命名為 `game.js`
2. 上傳到前台 GitHub repository 的 `assets/` 資料夾中
3. 確認 `https://the-plan.onrender.com` 是您實際的 Render 網址

**簡單記憶法**：
- **後端**：用 `game.backend.js`（動態，自動適應）
- **前台**：用 `game.frontend.js`（固定，指向 Render）
- **原本的 game.js**：兩個都不用，可以忽略

### 步驟 3：啟用 GitHub Pages

1. 在 `agree-game-frontend` repository 中，點擊 **Settings**
2. 在左側選單選擇 **Pages**
3. 在 **Source** 下方選擇：
   - **Branch**: `main`（或 `master`）
   - **Folder**: `/root`
4. 點擊 **Save**

### 步驟 4：取得前台網址

幾分鐘後，GitHub Pages 會提供一個網址，例如：
```
https://your-username.github.io/agree-game-frontend/
```

---

## 第三部分：測試與使用

### 測試前台

1. 開啟前台網址（例如：`https://your-username.github.io/agree-game-frontend/`）
2. 應該可以看到投票頁面
3. 點擊「同意」或「不同意」進行投票

### 使用後台

1. 開啟後端網址加上 `/admin`（例如：`https://agree-game.onrender.com/admin`）
2. 輸入您設定的密碼登入
3. 可以查看：
   - 投票統計
   - 最近回應記錄
   - 修改密碼
   - 清空投票紀錄

---

## 重要注意事項

### 1. Render 免費方案的限制

- **休眠機制**：免費方案在 15 分鐘沒有請求後會進入休眠
- **首次載入較慢**：休眠後第一次訪問可能需要幾秒鐘啟動
- **每月限額**：免費方案每月有 750 小時的運行時間

### 2. 資料庫持久化

- Render 的免費方案使用臨時檔案系統，重啟後資料會消失
- 如果需要永久保存投票記錄，建議：
  - 升級到付費方案（有持久化磁碟）
  - 或使用外部資料庫（如 PostgreSQL）

### 3. 安全性建議

- 務必設定強密的 `ADMIN_PASSWORD`
- 使用複雜的 `SECRET_KEY`（不要使用預設值）
- 定期更換密碼

### 4. 更新內容

如果需要修改題目或選項：

1. 修改 `data/questions.json` 檔案
2. 推送到 GitHub
3. Render 會自動重新部署

---

## 疑難排解

### 問題：前台無法連接後端

**解決方案**：
1. 確認 `game.js` 中的 `API_BASE_URL` 是否正確
2. 確認 Render 的服務是否正常運行
3. 檢查瀏覽器開發者工具的 Console 和 Network 標籤

### 問題：投票後沒有反應

**解決方案**：
1. 檢查 Render 的 Logs 是否有錯誤訊息
2. 確認 `data/questions.json` 格式正確
3. 確認資料庫檔案有寫入權限

### 問題：後台無法登入

**解決方案**：
1. 確認密碼是否正確
2. 如果忘記密碼，可以在 Render 的 Environment Variables 中重新設定 `ADMIN_PASSWORD`

---

## 聯絡與支援

如果有問題，請檢查：
1. Render 的 Logs（部署和運行日誌）
2. 瀏覽器開發者工具的錯誤訊息
3. GitHub repository 的檔案是否正確

---

## 部署檢查清單

- [ ] 後端 repository 已推送到 GitHub
- [ ] Render Web Service 已建立並運行
- [ ] 已設定 `SECRET_KEY` 和 `ADMIN_PASSWORD`
- [ ] 前台 repository 已推送到 GitHub
- [ ] 已修改 `game.js` 中的 API_BASE_URL
- [ ] GitHub Pages 已啟用
- [ ] 前台可以正常訪問
- [ ] 後台可以正常登入
- [ ] 投票功能正常運作

完成以上步驟後，您的投票遊戲就可以公開使用了！