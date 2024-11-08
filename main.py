import logging
from logging.handlers import RotatingFileHandler
import shutil

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.service import Service
from datetime import datetime
import os
from dotenv import load_dotenv
import time
from functools import wraps


load_dotenv()


def extract_and_parse_dates(date_string):
    # Split the string by '|'
    parts = date_string.split('|')

    # First date is either in parts[0] (which might contain '/')
    # Second date will be parts[1] and parts[2] joined by '|'

    try:
        # Parse first date (DD/MM/YYYY or D/M/YYYY)
        first_date = datetime.strptime(parts[0], '%d/%m/%Y')

        # Parse second date (MM|YYYY or M|YYYY)
        second_date_str = f"{parts[1]}|{parts[2]}"
        second_date = datetime.strptime(second_date_str.replace('|', '/'), '%m/%Y')

        return first_date, second_date
    except ValueError as e:
        return None, None


def retry_on_stale_element(retries=3, delay=1):
    """Decorator to retry on StaleElementReferenceException"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except StaleElementReferenceException as e:
                    if attempt == retries - 1:  # Last attempt
                        raise  # Re-raise the last exception
                    instance = args[0]  # Get class instance from method args
                    instance.logger.warning(
                        f"StaleElementReferenceException occurred. Attempt {attempt + 1}/{retries}. "
                        f"Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
            return None
        return wrapper
    return decorator


class ClaroInvoiceScraper:
    def __init__(self, log_level=logging.INFO):

        self.setup_logging(log_level)

        # Configure Chrome options
        self.options = webdriver.ChromeOptions()
        self.service = Service(executable_path=os.getenv('CHROMEDRIVER_PATH'))
        # Set download directory to current working directory
        self.download_dir = os.path.join(os.getcwd(), "downloads")
        self.download_temp_dir = os.path.join(self.download_dir, "tmp")
        os.makedirs(self.download_dir, exist_ok=True)
        self.options.add_argument("--excludeSwitches=enable-automation")
        self.options.add_argument("--excludeSwitches=enable-logging")
        prefs = {
            'credentials_enable_service': False,
            'profile': {
                'password_manager_enabled': False
            },
            "download.default_directory": self.download_temp_dir,
            "download.prompt_for_download": False,
            'download.directory_upgrade': True,
            "plugins.always_open_pdf_externally": True,
        }
        self.options.add_experimental_option('prefs', prefs)
        self.options.set_capability('unhandledPromptBehavior', 'dismiss')
        self.options.add_argument('--disable-extensions')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-notifications')
        self.options.add_argument('--disable-popup-blocking')
        self.options.add_argument("--verbose")

        self.driver = webdriver.Chrome(service=self.service, options=self.options)
        self.wait = WebDriverWait(self.driver, 10)

        self.logger.info(f"Initialized FileDownloader for pdf files")
        self.logger.debug(f"Using temporary directory: {self.download_temp_dir}")
        self.logger.debug(f"Using data directory: {self.download_dir}")

        self.logger = logging.getLogger(f'FileDownloader_{id(self)}')

        # Clear any existing temporary files
        self.clear_tmp_directory()

    def setup_logging(self, log_level):
        """Setup logging configuration"""
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)

        # Initialize the logger
        logger = logging.getLogger(f'FileDownloader_{id(self)}')
        logger.setLevel(log_level)

        # Remove any existing handlers (in case of re-initialization)
        if logger.handlers:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

        # Create handlers
        # File handler with rotation
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'file_downloader.log'),
            maxBytes=1024 * 1024,  # 1MB
            backupCount=5
        )
        # Console handler
        console_handler = logging.StreamHandler()

        # Set levels
        file_handler.setLevel(log_level)
        console_handler.setLevel(log_level)

        # Create formatters and add it to handlers
        log_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(log_format)
        console_handler.setFormatter(log_format)

        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        self.logger = logger

    def clear_tmp_directory(self):
        """Clear temporary directory of any existing files"""
        self.logger.debug(f"Clearing temporary directory: {self.download_temp_dir}")
        for file in os.listdir(self.download_temp_dir):
            file_path = os.path.join(self.download_temp_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    self.logger.debug(f"Deleted temporary file: {file}")
            except Exception as e:
                self.logger.error(f"Error deleting {file_path}: {str(e)}")

    def login(self):
        """Handle login process"""
        try:
            self.driver.get("https://contaonline.claro.com.br/webbow/login/initPJ_oqe.do")
            # Find and fill login form
            username = self.wait.until(EC.presence_of_element_located((By.NAME, "userVO.loginCode")))
            password = self.driver.find_element(By.NAME, "userVO.password")

            username.send_keys(os.getenv('CLARO_USERNAME'))
            password.send_keys(os.getenv('CLARO_PASSWORD'))

            # Click login button
            login_button = self.driver.find_element(By.CLASS_NAME, "GifButtonPtr")
            login_button.click()

            self.logger.info(f"Login sent: {self.driver.current_url}")

            # Wait for the new window to open and switch to it
            WebDriverWait(self.driver, 10).until(lambda d: len(d.window_handles) > 1)

            # Get all window handles
            window_handles = self.driver.window_handles

            # Switch to the new window (last window handle in the list)
            self.driver.switch_to.window(window_handles[-1])

            # Wait for redirect to welcome page

            WebDriverWait(self.driver, 10).until(
                lambda driver: "bemVindoPJ.do" in self.driver.current_url
            )

            # Handle popup if present
            try:
                close_btn = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "close-btn"))
                )
                close_btn.click()
                # self.handle_popup()
            except TimeoutException:
                print("No popup found or already closed")

            return True

        except TimeoutException:
            self.logger.error("Login failed - timeout")
            return False

    def handle_popup(self, selector_type=By.CSS_SELECTOR, selector_value="close-btn"):
        """Handle any popup that appears after login"""
        try:
            popup_close = self.wait.until(EC.presence_of_element_located((selector_type, selector_value)))
            popup_close.click()
        except TimeoutException:
            self.logger.error("No popup found or already closed")

    def navigate_to_invoices(self):
        """Navigate to the invoice download page"""
        try:
            # Click on Gerenciamento menu
            self.driver.get("https://contaonline.claro.com.br/webbow/downloadPDF/init.do")

            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.NAME, "billDueDate"))
            )

            return True
        except TimeoutException:
            self.logger.error("Failed to navigate to invoices page")
            return False

    def wait_for_download_complete(self, timeout=60, file_type: str = ".pdf"):
        """
        Wait for the download to complete
        Returns: (bool, str) - (success, filepath)
        """
        seconds = 0
        while seconds < timeout:
            time.sleep(1)
            files = os.listdir(self.download_temp_dir)

            # Check for incomplete downloads
            if any(f.endswith('.crdownload') or f.endswith('.tmp') for f in files):
                seconds += 1
                continue

            # Check for completed download of expected file type
            downloaded_files = [f for f in files if f.lower().endswith(file_type)]
            if downloaded_files:
                return True, os.path.join(self.download_temp_dir, downloaded_files[0])

            seconds += 1

        return False, None

    def move_and_rename_file(self, source_file, prefix=''):
        """
        Move file from tmp to data directory, adding prefix to original filename
        """
        if not source_file or not os.path.exists(source_file):
            return None

        # Get original filename and extension
        original_filename = os.path.basename(source_file)
        name_parts = os.path.splitext(original_filename)
        original_name = name_parts[0]
        original_ext = name_parts[1]  # Includes the dot

        # Generate new filename with prefix and date
        today_date = datetime.now().strftime('%Y-%m-%d')

        # Construct new filename with original extension
        new_name = f"{prefix}_{today_date}_{original_name}" if prefix else f"{today_date}_{original_name}"
        new_filename = os.path.join(self.download_dir, f"{new_name}{original_ext}")

        # Add counter if file exists
        counter = 1
        while os.path.exists(new_filename):
            new_filename = os.path.join(self.download_dir, f"{new_name}_{counter}{original_ext}")
            counter += 1

        # Move and rename file
        shutil.move(source_file, new_filename)
        return new_filename

    @retry_on_stale_element(retries=3, delay=1)
    def use_element_safely(self, driver, element_locator):
        """Safely click a button with retry mechanism"""
        # Wait for element to be both present and clickable
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(element_locator)
        )
        # Scroll element into view
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        # Wait a short time for any animations to complete
        time.sleep(0.5)

    def process_accounts(self):
        """Process all accounts in the select box"""
        try:
            account_select = Select(self.wait.until(EC.presence_of_element_located((By.NAME, "BAN"))))

            account_list = [option.get_attribute('value') for option in account_select.options]

            for account_number in account_list:
                # account_number = account.get_attribute("value")

                # account.click()
                select = Select(self.wait.until(EC.presence_of_element_located((By.NAME, "BAN"))))
                select.select_by_value(account_number)
                time.sleep(1)

                self.logger.info(f"Processing account: {account_number}")

                if account_number:

                    self.use_element_safely(self.driver, (By.NAME, "billDueDate"))

                    invoice_date_select = Select(self.wait.until(EC.presence_of_element_located((By.NAME, "billDueDate"))))

                    for invoice in invoice_date_select.options:

                        self.logger.info(f"Processing invoice: {invoice.text}")

                        invoice.click()

                        invoice_date_value = invoice.get_attribute("value")

                        if invoice_date_value:
                            invoice_dt, invoice_ref = extract_and_parse_dates(invoice_date_value)

                            self.logger.info(f"Selecting invoice: {account_number} - {invoice_dt}")

                            filename_prefix = f"conta_{account_number}_ref_{invoice_ref.strftime('%Y-%m')}_venc_{invoice_dt.strftime('%Y-%m-%d')}"

                            self.logger.info(f"Downloading invoice: {account_number} - {invoice_dt}")

                            time.sleep(1)

                            self.use_element_safely(self.driver, (By.CSS_SELECTOR, "input[src='/webbow/images/bot_ok.gif']"))

                            download_btn = self.driver.find_element(By.CSS_SELECTOR,
                                                                    "input[src='/webbow/images/bot_ok.gif']")
                            # Click download button
                            download_btn.click()

                            # Wait for download and rename file
                            time.sleep(2)  # Wait for download to start

                            download_success, downloaded_file = self.wait_for_download_complete()

                            if download_success:
                                self.logger.info(f"Download completed successfully: {os.path.basename(downloaded_file)}")

                                # Move and rename the file
                                final_path = self.move_and_rename_file(downloaded_file, filename_prefix)

                                if final_path:
                                    self.logger.info(f"File saved as: {os.path.basename(final_path)}")
                                else:
                                    self.logger.info(f"Error moving downloaded file")

                            else:
                                self.logger.info(f"Download timed out or no file found")
                                return None

        except NoSuchElementException:
            self.logger.error("No accounts found")
        except Exception as e:
            self.logger.error(f"Error processing accounts: {e}")

    def rename_latest_download(self, date_str, account_number):
        """Rename the latest downloaded file with date prefix"""
        # Wait for download to complete
        time.sleep(2)

        # Get the latest downloaded file
        files = sorted(
            [f for f in os.listdir(self.download_dir) if f.endswith('.pdf')],
            key=lambda x: os.path.getctime(os.path.join(self.download_dir, x))
        )

        if files:
            latest_file = files[-1]
            new_filename = f"{date_str}_account_{account_number}_{latest_file}"
            old_path = os.path.join(self.download_dir, latest_file)
            new_path = os.path.join(self.download_dir, new_filename)

            try:
                os.rename(old_path, new_path)
                self.logger.info(f"Renamed file to: {new_filename}")
            except OSError as e:
                self.logger.error(f"Error renaming file: {e}")

    def close(self):
        """Close the browser"""
        self.driver.quit()


def main():
    scraper = ClaroInvoiceScraper()

    try:
        if scraper.login():
            if scraper.navigate_to_invoices():
                scraper.process_accounts()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()