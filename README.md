## Claro Online Download
Download pdf invoices from https://contaonline.claro.com.br/


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