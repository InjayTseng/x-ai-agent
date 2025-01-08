**X(Twitter) Agent Framework Specification**。  
由於此框架是直接以瀏覽器自動化方式登入 Twitter，需確保沒有二階段驗證（2FA），或需在程式邏輯中處理 2FA 驗證流程。若 Twitter 出現頻繁的登入驗證或 CAPTCHA，也可能需要額外的人工干預。

---

# **Twitter Agent Framework Specification**

## **1. 概要**

此 Twitter Agent 旨在 24/7 透過 **Playwright** 自動與 Twitter 互動，不使用官方 API。具備以下功能：  
1. **學習**：從首頁推文及「按讚推文」中擷取推文，使用 OpenAI 產生摘要並儲存於資料庫。  
2. **回覆**：按照環境變數設定的「回覆間隔」（例如 30 分鐘），週期性檢索最新推文並發送回覆。  
3. **自動發文**：按照環境變數設定的「發文間隔」（例如 120 分鐘），定期彙整學習內容並發表心得推文。

---

## **2. 功能需求**

### **輸入**
1. **Twitter 帳號名稱**（`account_name`）  
2. **Twitter 密碼**（`password`）  
3. **Twitter 電子郵件**（`email`）  
4. **環境變數**：  
   - `REPLY_INTERVAL`：回覆他人的間隔（預設 30 分鐘）。  
   - `POST_INTERVAL`：自動發文的間隔（預設 120 分鐘）。  
   - `OPENAI_API_KEY`：用於 OpenAI NLP 的金鑰。  

### **輸出**
1. **資料庫**：包含推文、摘要、回覆與自動生成的推文紀錄。  
2. **回覆推文**：對偵測到的推文進行檢索後產生之回覆文字。  
3. **自動推文**：以過去一段時間的推文摘要內容彙整而成的心得推文。

---

## **3. 技術架構**

### **技術堆疊**
1. **程式語言**：Python 3.8+  
2. **瀏覽器自動化**：**Playwright**  
   - 用於模擬人工登入 Twitter，並進行擷取推文、回覆推文、發表推文等操作。  
3. **自然語言處理**：OpenAI API  
4. **資料庫**：SQLite（未來可視需求升級至更大型的關聯式資料庫）  
5. **檢索增強生成（RAG）**：以 SQLite 進行關鍵字檢索匹配，提供上下文給 OpenAI 以生成更合適的回覆或推文內容。

---

## **4. 資料庫設計**

### **資料表結構**

#### `tweets` 表
| 欄位名稱          | 型態         | 描述                                  |
|-------------------|-------------|---------------------------------------|
| `id`              | INTEGER     | 主鍵，自增                            |
| `original_text`   | TEXT        | 推文原始內容                          |
| `summary`         | TEXT        | 內容摘要                              |
| `source_account`  | TEXT        | 推文來源帳號                          |
| `timestamp`       | DATETIME    | 推文擷取時間                          |

#### `replies` 表
| 欄位名稱          | 型態         | 描述                                  |
|-------------------|-------------|---------------------------------------|
| `id`              | INTEGER     | 主鍵，自增                            |
| `tweet_id`        | INTEGER     | 與 `tweets.id` 對應                   |
| `reply_text`      | TEXT        | 回覆內容                              |
| `timestamp`       | DATETIME    | 回覆時間戳                            |

#### `posts` 表
| 欄位名稱          | 型態         | 描述                                  |
|-------------------|-------------|---------------------------------------|
| `id`              | INTEGER     | 主鍵，自增                            |
| `content`         | TEXT        | 自動產生的推文內容                    |
| `timestamp`       | DATETIME    | 發文時間戳                            |

---

## **5. 核心功能**

### **5.1 學習功能**

- **流程**：
  1. 以 Playwright 啟動瀏覽器，輸入 `account_name`、`password`、`email` 登入 Twitter。  
  2. 進入「首頁」與「按讚推文」頁面，擷取最新推文（含推文文字與作者）。  
  3. 使用 OpenAI API 為每則推文生成摘要。  
  4. 寫入 `tweets` 表（含原文與摘要）。  

- **範例函式**：
  ```python
  def fetch_and_learn_tweets(page):
      """
      1. 以 Playwright 的 page 物件擷取 Twitter 首頁與按讚推文。
      2. 使用 OpenAI 產生摘要。
      3. 寫入資料庫。
      """
      pass
  ```

### **5.2 回覆功能**

- **流程**：
  1. 依照 `REPLY_INTERVAL` 週期（例：30 分鐘）觸發。  
  2. 透過 Playwright 擷取目標推文（可從 Twitter 首頁或指定話題）。  
  3. 擷取關鍵字後，以 SQLite 中的 `tweets` 表進行關鍵字檢索（RAG）。  
  4. 使用檢索出的上下文呼叫 OpenAI，生成回覆文字。  
  5. 以 Playwright 進行自動回覆動作，並將回覆紀錄存入 `replies` 表。

- **範例函式**：
  ```python
  def reply_to_tweets(page):
      """
      使用 Playwright 擷取最新推文 -> RAG -> OpenAI 生成 -> 自動回覆 -> 寫入資料庫
      """
      pass
  ```

### **5.3 自動發文功能**

- **流程**：
  1. 依照 `POST_INTERVAL` 週期（例：120 分鐘）觸發。  
  2. 從 `tweets` 表中取得過去該間隔時間內的推文摘要。  
  3. 使用 OpenAI 進行彙整，生成心得推文。  
  4. 透過 Playwright 自動將這段內容發送為推文，並將發文內容寫入 `posts` 表。

- **範例函式**：
  ```python
  from datetime import datetime, timedelta
  import sqlite3

  def post_summary(page):
      """
      每 120 分鐘彙整 tweets -> OpenAI -> 發文
      """
      pass
  ```

---

## **6. 定時排程與執行**

### **任務排程**

- 透過 `APScheduler` 或相似排程工具，定時呼叫下列函式：
  - `reply_to_tweets`：以 `REPLY_INTERVAL` 為週期  
  - `post_summary`：以 `POST_INTERVAL` 為週期  

### **排程程式碼範例**

```python
import os
from apscheduler.schedulers.background import BackgroundScheduler

REPLY_INTERVAL = int(os.getenv("REPLY_INTERVAL", 30))   # 預設 30 分鐘
POST_INTERVAL = int(os.getenv("POST_INTERVAL", 120))    # 預設 120 分鐘

scheduler = BackgroundScheduler()

# 假設這兩個函式在其他地方已定義
scheduler.add_job(reply_to_tweets, 'interval', minutes=REPLY_INTERVAL)
scheduler.add_job(post_summary, 'interval', minutes=POST_INTERVAL)

scheduler.start()

try:
    while True:
        pass
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
```

---

## **7. 部署**

### **部署環境**
- **雲端平臺**：AWS EC2、Heroku、Vercel、Railway 等皆可  
- **環境需求**：  
  - Python 3.8+  
  - 安裝 Playwright 及其瀏覽器驅動（`playwright install`）  
- **設定**：
  - `.env` 檔：儲存 `account_name`, `password`, `email`, `OPENAI_API_KEY` 等敏感資訊  
  - 需確保程式在背景不斷執行（例如使用 Supervisor、Systemd、PM2 for Python 等方式）

### **步驟**
1. **安裝依賴**：
   ```bash
   pip install playwright openai apscheduler python-dotenv sqlite3
   playwright install
   ```
2. **初始化資料庫**，建立 `tweets`、`replies`、`posts` 三張表。  
3. **設定 .env** （範例）：
   ```
   account_name=YourTwitterAccount
   password=YourPassword
   email=YourEmail
   REPLY_INTERVAL=30
   POST_INTERVAL=120
   OPENAI_API_KEY=your_openai_key
   ```
4. 部署至伺服器並確保程式可在背景持續執行。

---

## **8. 安全與擴充**

### **安全性**
- 敏感資訊放於 `.env` 檔或以雲端密鑰管理方式儲存，不要在程式碼中硬編碼。  
- 考量 Twitter 可能要求 2FA（兩步驟驗證）或遇到 CAPTCHA，需要預留額外處理邏輯。  
- OpenAI API Key 使用時也要留意限額與費用。

### **擴充性**
- **多帳號支援**：若需要管理多個 Twitter 帳號，可在資料庫新增表格或欄位，並於程式中以迴圈方式分批執行登入、回覆、發文等操作。  
- **向量化檢索**：若日後需要更精準的 RAG，可以將推文內容向量化，並使用向量資料庫替代關鍵字檢索。  
- **資料分析**：可在系統內部增設分析模組，查看每條自動回覆或自動推文的互動成效（讚數、轉推數、回覆數）。

---

以上即為 **不依賴 Twitter API、完全使用 Playwright 瀏覽器自動化**，並以「Twitter 帳號名稱 (`account_name`)、密碼 (`password`)、電子郵件 (`email`)」即可開始運行的 **Twitter Agent Framework Specification**。此方案可協助你在不需申請 Twitter 開發者權限的情況下完成自動化操作，但需注意登入及穩定性問題（CAPTCHA、2FA 等），並妥善管理敏感資訊。祝開發順利!