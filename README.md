## Claro Online Download
Download pdf invoices from https://contaonline.claro.com.br/

Will save everything to downloads folder.

All invoices will be saved with a prefix using the account, due date and ref date.

`conta_101216026_ref_2023-09_venc_2023-11-25_2024-11-07_101216026_25-11-2023_9_2023_53.pdf`

### Download chromedriver

Mac: https://googlechromelabs.github.io/chrome-for-testing/

Windows: https://sites.google.com/chromium.org/driver/

### Configuration

create .env file with the following content:

```
CLARO_USERNAME = "login"
CLARO_PASSWORD = "password"
CHROMEDRIVE_PATH = "/Users/user/my_code/bin/chromedriver/"
```

### For fixing macos permissions

```
which chromedriver 
chmod +x /opt/homebrew/bin/chromedriver 
```