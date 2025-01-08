from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import os
import time
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterBrowser:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        
    def start(self, headless: bool = True) -> None:
        """Start the browser instance"""
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            self.context = self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = self.context.new_page()
            
            # Add stealth scripts
            self._add_stealth_scripts()
            logger.info("Browser started successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to start browser: {str(e)}")
            return False
        
    def login(self, email: str, password: str, account_name: str) -> bool:
        """Login to Twitter account with advanced error handling"""
        try:
            # Navigate to Twitter login page
            logger.info("Navigating to Twitter login page...")
            self.page.goto('https://twitter.com/i/flow/login', wait_until='networkidle')
            time.sleep(3)  # Allow any redirects and JS to complete
            
            # Enter email - using Twitter's internal test IDs
            logger.info("Entering email...")
            try:
                # Wait for the login form to be fully loaded
                self.page.wait_for_selector('div[class*="css-175oi2r"]', timeout=10000)
                time.sleep(1)
                
                # Try multiple methods to find and fill the email input
                email_input = None
                for selector in [
                    'input[autocomplete="username"]',
                    'input[name="text"]',
                    'input[type="text"]'
                ]:
                    try:
                        email_input = self.page.wait_for_selector(selector, timeout=3000, state='visible')
                        if email_input:
                            break
                    except PlaywrightTimeout:
                        continue
                
                if not email_input:
                    raise Exception("Could not find email input field")
                
                # Clear and fill email
                email_input.click()
                email_input.fill('')  # Clear first
                email_input.type(email, delay=100)  # Type slowly
                time.sleep(1)
                
                # Try multiple methods to click the Next button
                clicked = False
                methods = [
                    lambda: self.page.click('div[role="button"]:has-text("Next")'),
                    lambda: self.page.click('[data-testid="LoginForm_Login_Button"]'),
                    lambda: self.page.keyboard.press('Enter'),
                    lambda: self.page.evaluate('document.querySelector("div[role=\\"button\\"]").click()')
                ]
                
                for method in methods:
                    try:
                        method()
                        clicked = True
                        logger.info("Successfully clicked Next button")
                        break
                    except Exception as e:
                        logger.debug(f"Click method failed: {str(e)}")
                        continue
                
                if not clicked:
                    raise Exception("Could not click Next button")
                
                time.sleep(2)
                
                # Handle username verification if needed
                if self.page.locator('input[data-testid="ocfEnterTextTextInput"]').is_visible(timeout=3000):
                    logger.info("Username verification required...")
                    username_input = self.page.locator('input[data-testid="ocfEnterTextTextInput"]')
                    username_input.fill(account_name)
                    time.sleep(1)
                    
                    # Try multiple methods to click Next after username
                    clicked = False
                    username_next_methods = [
                        lambda: self.page.click('div[role="button"]:has-text("Next")'),
                        lambda: self.page.click('[data-testid="LoginForm_Login_Button"]'),
                        lambda: self.page.keyboard.press('Enter'),
                        lambda: self.page.evaluate('document.querySelector("div[role=\\"button\\"]").click()')
                    ]
                    
                    for method in username_next_methods:
                        try:
                            method()
                            clicked = True
                            logger.info("Successfully clicked Next after username")
                            break
                        except Exception as e:
                            logger.debug(f"Username next click method failed: {str(e)}")
                            continue
                    
                    if not clicked:
                        raise Exception("Could not click Next after username")
                    
                    time.sleep(2)
                
                # Wait for and enter password
                logger.info("Entering password...")
                password_input = self.page.wait_for_selector('input[name="password"]', timeout=10000)
                if not password_input:
                    raise Exception("Could not find password field")
                
                password_input.click()
                password_input.fill(password)
                time.sleep(1)
                
                # Try multiple methods to click the Login button
                clicked = False
                login_methods = [
                    lambda: self.page.click('div[role="button"]:has-text("Log in")'),
                    lambda: self.page.click('[data-testid="LoginForm_Login_Button"]'),
                    lambda: self.page.keyboard.press('Enter'),
                    lambda: self.page.evaluate('document.querySelector("div[role=\\"button\\"]").click()')
                ]
                
                for method in login_methods:
                    try:
                        method()
                        clicked = True
                        logger.info("Successfully clicked Login button")
                        break
                    except Exception as e:
                        logger.debug(f"Login click method failed: {str(e)}")
                        continue
                
                if not clicked:
                    raise Exception("Could not click Login button")
                
                # Check for successful login
                success_indicators = [
                    '[data-testid="primaryColumn"]',
                    '[data-testid="SideNav_NewTweet_Button"]',
                    'a[aria-label="Profile"]',
                    'div[data-testid="AppTabBar_Home_Link"]'
                ]
                
                for indicator in success_indicators:
                    try:
                        self.page.wait_for_selector(indicator, timeout=5000)
                        logger.info("Successfully logged in to Twitter")
                        return True
                    except PlaywrightTimeout:
                        continue
                
                # Check for errors
                error_messages = [
                    ('text=Wrong password', 'Incorrect password provided'),
                    ('text=Verify your identity', 'Twitter requires identity verification'),
                    ('text=Something went wrong', 'Twitter encountered an error'),
                    ('text=Unusual login activity', 'Twitter detected unusual login activity'),
                    ('text=Too many login attempts', 'Too many failed login attempts'),
                    ('text=Account locked', 'Account has been locked')
                ]
                
                for selector, message in error_messages:
                    if self.page.locator(selector).is_visible(timeout=1000):
                        logger.error(f"Login failed: {message}")
                        # Take error screenshot
                        self.page.screenshot(path=f'login_error_{message.replace(" ", "_")}.png')
                        return False
                
                logger.error("Login failed: Unknown error")
                self.page.screenshot(path='login_error_unknown.png')
                return False
                
            except Exception as e:
                logger.error(f"Login step failed: {str(e)}")
                self.page.screenshot(path='login_error_exception.png')
                return False
                
        except Exception as e:
            logger.error(f"Login failed with exception: {str(e)}")
            return False
    
    def close(self) -> None:
        """Close all browser resources"""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Browser resources closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser resources: {str(e)}")
    
    def get_page(self):
        """Return the current page object"""
        return self.page
    
    def _add_stealth_scripts(self):
        """Add scripts to help avoid detection"""
        self.page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        """)
        
    def is_logged_in(self) -> bool:
        """Check if currently logged in to Twitter"""
        try:
            return self.page.locator('[data-testid="primaryColumn"]').is_visible(timeout=1000)
        except:
            return False
