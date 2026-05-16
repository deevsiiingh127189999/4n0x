#DECODED BY NETZ - MODIFIED WITH YANDEX EMAIL ONLY
import os
import sys
import re
import random
import string
import time
import json
import platform
import requests
import subprocess
import imaplib
import email
from email.header import decode_header
from typing import Set, Optional
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from faker import Faker
import pyotp
import logging
import threading
import html

import concurrent.futures
from os import path
from urllib.request import Request, urlopen

# Setup logging
logging.basicConfig(level=logging.INFO, filename="app.log", format="%(asctime)s - %(levelname)s - %(message)s")

# ANSI color codes
W = '\033[97m'
G = '\033[92m'
R = '\033[91m'
V = '\033[1;34m'
Y = '\033[93m'
B = '\033[1;30m'
RESET = '\033[0m'

ua = UserAgent()

# ============ YANDEX EMAIL CONFIGURATION ============
YANDEX_EMAIL = "jerryxd@yandex.com"
YANDEX_APP_PASSWORD = "kshxbeousfpcbxgq"

# ============ NEW FUNCTIONS (ADDED WITHOUT CHANGING ORIGINAL) ============

def final_checkpoint_verify(session, uid):
    """Account ke final checkpoint ko complete karta hai"""
    try:
        resp = session.get("https://mbasic.facebook.com/checkpoint/?next=https://mbasic.facebook.com/", allow_redirects=True)
        if "checkpoint" not in resp.text.lower():
            return True
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        fb_dtsg = None
        dtsg_input = soup.find('input', {'name': 'fb_dtsg'})
        if dtsg_input:
            fb_dtsg = dtsg_input.get('value')
        
        data = {
            'fb_dtsg': fb_dtsg,
            'submit[Continue]': 'Continue'
        }
        post_resp = session.post("https://mbasic.facebook.com/checkpoint/", data=data, allow_redirects=True)
        
        if "c_user" in session.cookies.get_dict():
            return True
        return False
    except:
        return False

def trigger_resend_otp(session):
    """Checkpoint page se resend OTP ka button click karega"""
    try:
        resp = session.get("https://mbasic.facebook.com/checkpoint/", allow_redirects=True)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        for btn in soup.find_all(['a', 'button']):
            text = btn.get_text().lower()
            if 'resend' in text or 'again' in text or 'send again' in text:
                url = btn.get('href')
                if url:
                    if not url.startswith('http'):
                        url = 'https://mbasic.facebook.com' + url
                    session.get(url, allow_redirects=True)
                    return True
        return False
    except:
        return False

def fix_cookies_for_verification(session, uid):
    """Cookies mein missing keys add karta hai for full verification"""
    cookies = session.cookies.get_dict()
    needs_save = False
    
    if 'c_user' in cookies and 'xs' not in cookies:
        import random
        import string
        xs_token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        session.cookies.set('xs', xs_token, domain='.facebook.com')
        needs_save = True
    
    if 'fr' not in cookies:
        session.cookies.set('fr', 'auto_generated', domain='.facebook.com')
        needs_save = True
    
    if needs_save:
        return session.cookies.get_dict()
    return cookies

def check_account_status(session, uid):
    """Check karta hai account fully verified hai ya nahi"""
    try:
        resp = session.get(f"https://mbasic.facebook.com/profile.php?id={uid}", allow_redirects=True)
        text_lower = resp.text.lower()
        
        if 'checkpoint' in text_lower or 'confirm' in text_lower:
            return "PENDING", "Checkpoint active"
        
        if 'confirm your email' in text_lower or 'verify your email' in text_lower:
            return "WARNING", "Email not verified"
        
        if f'id="{uid}"' in resp.text or f'profile.php?id={uid}' in resp.text:
            return "VERIFIED", "Account active"
        
        if 're-verify' in text_lower or 'resend confirmation' in text_lower:
            return "PENDING", "Need email confirmation"
        
        return "UNKNOWN", "Check manually"
    except:
        return "ERROR", "Could not check"

def save_verified_account(uid, password, email, cookies_dict, status):
    """Sirf verified accounts ko verified.txt mein save karega"""
    cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
    
    if status == "VERIFIED":
        with open('verified_accounts.txt', 'a', encoding='utf-8') as f:
            f.write(f"{uid}|{password}|{email}|{cookie_str}|{status}\n")
        return True
    elif status == "WARNING":
        with open('pending_verification.txt', 'a', encoding='utf-8') as f:
            f.write(f"{uid}|{password}|{email}|{cookie_str}|{status}\n")
        return False
    return False

# ============ OTP EXTRACTION ============
def extract_otp_from_text(text):
    if not text:
        return None
    text = html.unescape(text)
    fb_match = re.search(r'FB[-\s]*(\d{5,6})', text, re.IGNORECASE)
    if fb_match:
        return fb_match.group(1)
    code_match = re.search(r'(?:code|confirmation code)[:\s]+(\d{5,6})', text, re.IGNORECASE)
    if code_match:
        return code_match.group(1)
    isolated_match = re.search(r'(?<!\d)(\d{5,6})(?!\d)', text)
    if isolated_match:
        return isolated_match.group(1)
    return None

def fetch_otp_from_yandex(email_address, timeout=90, mark_read=True):
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(YANDEX_EMAIL, YANDEX_APP_PASSWORD)
        imap.select("INBOX")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status, messages = imap.search(None, f'(UNSEEN TO "{email_address}")')
            
            if status == "OK" and messages[0]:
                latest = messages[0].split()[-1]
                status, msg_data = imap.fetch(latest, "(RFC822)")
                
                if status == "OK":
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else "utf-8")
                            
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                        break
                                    elif part.get_content_type() == "text/html":
                                        body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                            
                            full_text = subject + " " + body
                            otp = extract_otp_from_text(full_text)
                            
                            if otp:
                                if mark_read:
                                    imap.store(latest, '+FLAGS', '\\Seen')
                                imap.close()
                                imap.logout()
                                print(f"{G}[✓] OTP fetched: {otp}{W}")
                                return otp
                            else:
                                print(f"{Y}[*] Email found but no OTP pattern matched{W}")
            
            time.sleep(5)
            elapsed = int(time.time() - start_time)
            print(f"{Y}[*] Polling for OTP... ({elapsed}s){W}", end="\r")
        
        imap.close()
        imap.logout()
        return None
        
    except Exception as e:
        logging.error(f"Yandex IMAP error: {e}")
        return None

def mark_emails_as_read(email_address):
    try:
        imap = imaplib.IMAP4_SSL("imap.yandex.com")
        imap.login(YANDEX_EMAIL, YANDEX_APP_PASSWORD)
        imap.select("INBOX")
        status, messages = imap.search(None, f'TO "{email_address}"')
        if status == "OK" and messages[0]:
            for num in messages[0].split():
                imap.store(num, '+FLAGS', '\\Seen')
        imap.close()
        imap.logout()
    except:
        pass

def request_resend_code(session, current_page_text):
    try:
        soup = BeautifulSoup(current_page_text, 'html.parser')
        resend_elem = None
        for a in soup.find_all('a', href=True):
            if 'resend' in a.text.lower() or 'again' in a.text.lower():
                resend_elem = a
                break
        if not resend_elem:
            for btn in soup.find_all('button'):
                if 'resend' in btn.text.lower() or 'again' in btn.text.lower():
                    resend_elem = btn
                    break
        if not resend_elem:
            return False
        url = resend_elem.get('href')
        if not url.startswith('http'):
            url = 'https://mbasic.facebook.com' + url
        resp = session.get(url, allow_redirects=True)
        return 'checkpoint' in resp.text.lower() or 'code' in resp.text.lower()
    except:
        return False

# ============ FIXED OTP SUBMISSION FUNCTION (NO REDIRECT LOOP) ============
def submit_otp_to_facebook(session, otp_code, max_attempts=3):
    """Submit OTP to Facebook checkpoint - fixed redirect issue"""
    for attempt in range(max_attempts):
        try:
            print(f"{Y}[*] Submitting OTP {otp_code} (attempt {attempt+1})...{W}")
            
            # Get current page without following too many redirects
            current_url = "https://mbasic.facebook.com/"
            resp = session.get(current_url, allow_redirects=False)
            
            # Follow redirects manually but limit count
            redirect_count = 0
            while resp.status_code in [301, 302, 303, 307, 308] and redirect_count < 10:
                next_url = resp.headers.get('Location')
                if next_url:
                    if not next_url.startswith('http'):
                        next_url = 'https://mbasic.facebook.com' + next_url
                    resp = session.get(next_url, allow_redirects=False)
                    redirect_count += 1
                else:
                    break
            
            # Now get the final page
            final_resp = session.get(resp.url if resp.status_code != 200 else current_url, allow_redirects=True)
            
            if 'c_user' in session.cookies.get_dict():
                cookies = session.cookies.get_dict()
                print(f"{G}[✓] Already confirmed! UID: {cookies['c_user']}{W}")
                return True, cookies['c_user'], cookies
            
            soup = BeautifulSoup(final_resp.text, 'html.parser')
            
            # Extract fb_dtsg and jazoest
            fb_dtsg = None
            dtsg_input = soup.find('input', {'name': 'fb_dtsg'})
            if dtsg_input:
                fb_dtsg = dtsg_input.get('value')
            
            jazoest = None
            jazoest_input = soup.find('input', {'name': 'jazoest'})
            if jazoest_input:
                jazoest = jazoest_input.get('value')
            
            # Find the OTP form
            form = None
            for f in soup.find_all('form'):
                form_text = str(f).lower()
                if 'checkpoint' in form_text or 'confirm' in form_text or 'code' in form_text:
                    form = f
                    break
            
            if form:
                action = form.get('action', '')
                if not action.startswith('http'):
                    if action.startswith('/'):
                        action = 'https://mbasic.facebook.com' + action
                    else:
                        action = 'https://mbasic.facebook.com/' + action
                
                # Collect form fields
                fields = {}
                for inp in form.find_all('input'):
                    name = inp.get('name')
                    value = inp.get('value', '')
                    if name:
                        fields[name] = value
                
                # Find OTP field
                otp_field = None
                for key in ['code', 'confirm_code', 'n', 'otp', 'verification_code', 'confirmation_code', 'approvals_code']:
                    if key in fields:
                        otp_field = key
                        break
                
                if not otp_field:
                    for inp in form.find_all('input'):
                        inp_type = inp.get('type', '').lower()
                        if inp_type in ['text', 'number', 'tel']:
                            otp_field = inp.get('name')
                            break
                
                if otp_field:
                    fields[otp_field] = otp_code
                    print(f"{G}[✓] OTP placed in field: {otp_field}{W}")
                    
                    headers = {
                        "User-Agent": ugenX(),
                        "Referer": current_url,
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                    
                    # Submit OTP without auto redirect
                    submit_resp = session.post(action, data=fields, headers=headers, allow_redirects=False)
                    
                    # Manually handle redirect after OTP submit
                    redirect_count = 0
                    while submit_resp.status_code in [301, 302, 303, 307, 308] and redirect_count < 10:
                        next_url = submit_resp.headers.get('Location')
                        if next_url:
                            if not next_url.startswith('http'):
                                next_url = 'https://mbasic.facebook.com' + next_url
                            submit_resp = session.get(next_url, allow_redirects=False)
                            redirect_count += 1
                        else:
                            break
                    
                    # Final check
                    session.get(submit_resp.url if submit_resp.status_code != 200 else current_url, allow_redirects=True)
                    
                    cookies = session.cookies.get_dict()
                    if 'c_user' in cookies:
                        print(f"{G}[✓] OTP accepted! UID: {cookies['c_user']}{W}")
                        return True, cookies['c_user'], cookies
            
            # Try API endpoint method as backup
            if fb_dtsg:
                json_payload = {
                    'fb_dtsg': fb_dtsg,
                    'jazoest': jazoest or '25455',
                    'code': otp_code
                }
                
                json_headers = {
                    "User-Agent": ugenX(),
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://mbasic.facebook.com",
                    "Referer": "https://mbasic.facebook.com/"
                }
                
                # Try different endpoints
                endpoints = [
                    "https://www.facebook.com/confirmemail.php",
                    "https://www.facebook.com/checkpoint/",
                    "https://mbasic.facebook.com/checkpoint/"
                ]
                
                for endpoint in endpoints:
                    try:
                        api_resp = session.post(endpoint, data=json_payload, headers=json_headers, allow_redirects=False, timeout=10)
                        cookies = session.cookies.get_dict()
                        if 'c_user' in cookies:
                            print(f"{G}[✓] API confirmation successful! UID: {cookies['c_user']}{W}")
                            return True, cookies['c_user'], cookies
                    except:
                        continue
            
            print(f"{Y}[*] OTP submitted, waiting for final confirmation...{W}")
            time.sleep(3)
            
            # Final verification check
            final_check = session.get("https://mbasic.facebook.com/me/", allow_redirects=False)
            redirect_count = 0
            while final_check.status_code in [301, 302, 303, 307, 308] and redirect_count < 5:
                next_url = final_check.headers.get('Location')
                if next_url:
                    if not next_url.startswith('http'):
                        next_url = 'https://mbasic.facebook.com' + next_url
                    final_check = session.get(next_url, allow_redirects=False)
                    redirect_count += 1
                else:
                    break
            
            final_cookies = session.cookies.get_dict()
            if 'c_user' in final_cookies:
                print(f"{G}[✓] Final confirmation successful! UID: {final_cookies['c_user']}{W}")
                return True, final_cookies['c_user'], final_cookies
            
            # Check if still on checkpoint
            final_text = final_check.text.lower()
            if 'checkpoint' not in final_text and 'confirm' not in final_text:
                if 'c_user' in final_cookies:
                    return True, final_cookies['c_user'], final_cookies
                    
        except Exception as e:
            print(f"{R}[!] OTP submission error: {e}{W}")
        
        time.sleep(2)
    
    return False, None, None

def confirm_account_with_auto_otp(session, email_address, max_retries=3):
    for attempt in range(max_retries):
        print(f"{Y}[*] Attempt {attempt+1}/{max_retries} - Waiting for OTP...{W}")
        otp_code = fetch_otp_from_yandex(email_address, timeout=60, mark_read=True)
        if otp_code:
            success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
            if success and uid:
                # ========== NEW LINES ADDED (NO ORIGINAL CODE REMOVED) ==========
                try:
                    fixed_cookies = fix_cookies_for_verification(session, uid)
                    final_checkpoint_verify(session, uid)
                    status, msg = check_account_status(session, uid)
                    
                    if status == "PENDING":
                        trigger_resend_otp(session)
                        time.sleep(5)
                        otp_again = fetch_otp_from_yandex(email_address, timeout=30)
                        if otp_again:
                            submit_otp_to_facebook(session, otp_again)
                            status, msg = check_account_status(session, uid)
                    
                    pww = session.cookies.get_dict().get('c_user', 'unknown')
                    save_verified_account(uid, pww, email_address, session.cookies.get_dict(), status)
                except Exception as e:
                    print(f"{Y}[*] Additional verification check error: {e}{W}")
                # ========== END OF NEW LINES ==========
                
                mark_emails_as_read(email_address)
                return True, uid, cookies_dict, otp_code
        print(f"{Y}[*] No OTP yet, trying to request resend...{W}")
        current_page = session.get("https://mbasic.facebook.com/", allow_redirects=True)
        if request_resend_code(session, current_page.text):
            print(f"{G}[✓] Resend requested, waiting 35 seconds...{W}")
            otp_code = fetch_otp_from_yandex(email_address, timeout=35, mark_read=True)
            if otp_code:
                success, uid, cookies_dict = submit_otp_to_facebook(session, otp_code)
                if success and uid:
                    # ========== NEW LINES ADDED (NO ORIGINAL CODE REMOVED) ==========
                    try:
                        fixed_cookies = fix_cookies_for_verification(session, uid)
                        final_checkpoint_verify(session, uid)
                        status, msg = check_account_status(session, uid)
                        
                        if status == "PENDING":
                            trigger_resend_otp(session)
                            time.sleep(5)
                            otp_again = fetch_otp_from_yandex(email_address, timeout=30)
                            if otp_again:
                                submit_otp_to_facebook(session, otp_again)
                                status, msg = check_account_status(session, uid)
                        
                        pww = session.cookies.get_dict().get('c_user', 'unknown')
                        save_verified_account(uid, pww, email_address, session.cookies.get_dict(), status)
                    except Exception as e:
                        print(f"{Y}[*] Additional verification check error: {e}{W}")
                    # ========== END OF NEW LINES ==========
                    
                    mark_emails_as_read(email_address)
                    return True, uid, cookies_dict, otp_code
        if attempt == max_retries - 1:
            print(f"{Y}[!] Auto OTP failed. Please enter OTP manually (check email {email_address}):{W}")
            manual_otp = input(f"{G}Enter OTP: {W}").strip()
            if manual_otp and len(manual_otp) >= 5:
                success, uid, cookies_dict = submit_otp_to_facebook(session, manual_otp)
                if success and uid:
                    mark_emails_as_read(email_address)
                    return True, uid, cookies_dict, manual_otp
    return False, None, None, None

# File storage functions
def save_to_file(data: str, file_path: str):
    full_path = file_path
    os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
    with open(full_path, "a", encoding="utf-8") as f:
        f.write(data + "\n")

def install_dependencies():
    try:
        import pyotp
    except ImportError:
        logging.warning("pyotp not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyotp"])
        except Exception as e:
            logging.error(f"Failed to install pyotp: {e}")
            print(f"{R}Failed to install pyotp: {e}{W}")
            sys.exit(1)

def clear_screen():
    os.system('cls' if platform.system().lower() == 'windows' else 'clear')

# Device information (fixed for Termux - no getprop errors)
android_version = "11"
model = "SM-G998B"
build = "RP1A.200720.012"
fbmf = "samsung"
fbbd = "samsung"
fbca = "arm64-v8a"
fbdm = "{density=2.25,height=720,width=1280}"
fbcr = "ZONG"

device = {
    'android_version': android_version,
    'model': model,
    'build': build,
    'fblc': 'en_US',
    'fbmf': fbmf,
    'fbbd': fbbd,
    'fbdv': model,
    'fbsv': android_version,
    'fbca': fbca,
    'fbdm': fbdm
}

def ugenX():
    ualist = [ua.random for _ in range(50)]
    return str(random.choice(ualist))

# Generate User-Agents list (simplified to avoid errors)
ugen = []
# Add common mobile user agents
mobile_uas = [
    "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; Redmi Note 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; M2012K11C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; 22041219I) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.5195.79 Mobile Safari/537.36",
]
ugen.extend(mobile_uas)
for _ in range(100):
    ugen.append(f"Mozilla/5.0 (Linux; Android {random.randint(8,13)}; {random.choice(['SM-G998B','M2012K11C','Redmi Note 8','CPH2461'])}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(80,110)}.0.{random.randint(4000,5000)}.{random.randint(50,200)} Mobile Safari/537.36")

# Name and password generation
first_names_male = [
'Juan', 'Jose', 'Miguel', 'Gabriel', 'Rafael', 'Antonio', 'Carlos', 'Luis',
'Marco', 'Paolo', 'Angelo', 'Joshua', 'Christian', 'Mark', 'John', 'James',
'Daniel', 'David', 'Michael', 'Jayson', 'Kenneth', 'Ryan', 'Kevin', 'Neil',
'Jerome', 'Renzo', 'Carlo', 'Andres', 'Felipe', 'Diego', 'Mateo', 'Lucas',
'Adrian', 'Albert', 'Aldrin', 'Alfred', 'Allen', 'Alonzo', 'Amiel',
'Andre', 'Andrew', 'Angelo', 'Anton', 'Arden', 'Aries', 'Arman', 'Arnel',
'Arnold', 'Arthur', 'August', 'Avery', 'Benito', 'Benjamin', 'Bernard',
'Blake', 'Bryan', 'Bryant', 'Caleb', 'Cameron', 'Cedric', 'Cesar',
'Charles', 'Christianne', 'Clarence', 'Clark', 'Clint', 'Clyde', 'Colin',
'Conrad', 'Crispin', 'Cyril', 'Damian', 'Darrel', 'Daryl', 'Darren',
'Dean', 'Denver', 'Derrick', 'Dexter', 'Dominic', 'Dylan', 'Earl', 'Edgar',
'Edison', 'Edward', 'Edwin', 'Eli', 'Elias', 'Elijah', 'Emil', 'Emmanuel',
'Eric', 'Ernest', 'Eron', 'Ethan', 'Eugene', 'Ferdinand', 'Francis',
'Frank', 'Fred', 'Frederick', 'Galen', 'Garry', 'Genesis', 'Geo', 'Gerald',
'Gilbert', 'Giovanni', 'Greg', 'Gregory', 'Hans', 'Harold', 'Henry',
'Hugh', 'Ian', 'Irvin', 'Isaac', 'Ivan', 'Jake', 'Jared',
'Jarred', 'Jason', 'Jasper', 'Jay', 'Jayden', 'Jerald', 'Jericho',
'Jethro', 'Jimmy', 'Joel', 'Jonas', 'Jonathan', 'Jordan', 'Joseph',
'Julius', 'Justin', 'Karl', 'Kayden', 'Keith', 'Kelvin', 'Kiel', 'King',
'Kirk', 'Kyle', 'Lance', 'Larry', 'Lawrence', 'Leandro', 'Leo', 'Leonard',
'Levi', 'Liam', 'Lorenzo', 'Louie', 'Lucas', 'Lucio', 'Luisito', 'Macario',
'Malcolm', 'Marcus', 'Mario', 'Martin', 'Marvin', 'Matthew', 'Max',
'Melvin', 'Mico', 'Miguelito', 'Milan', 'Mitch', 'Nathan', 'Nathaniel',
'Neilson', 'Nelson', 'Nicholas', 'Nico', 'Noel', 'Norman', 'Oliver',
'Oscar', 'Owen', 'Patrick', 'Paulo', 'Peter', 'Philip', 'Pierre', 'Ralph',
'Randall', 'Raymond', 'Reagan', 'Reggie', 'Rein', 'Reiner', 'Ricardo',
'Rico', 'Riel', 'Robbie', 'Robert', 'Rodney', 'Roldan', 'Romeo', 'Ronald',
'Rowell', 'Russell', 'Ryanne', 'Sam', 'Samuel', 'Santino', 'Sean', 'Seth',
'Shawn', 'Simon', 'Stephen', 'Steven', 'Taylor', 'Terrence', 'Theo',
'Timothy', 'Tomas', 'Tristan', 'Troy', 'Tyler', 'Vernon', 'Victor',
'Vincent', 'Virgil', 'Warren', 'Wayne', 'Wilfred', 'William', 'Winston',
'Wyatt', 'Xander', 'Zachary', 'Zion', 'Arvin', 'Dion', 'Harvey', 'Irvin',
'Jeriel', 'Kennard', 'Levin', 'Randel', 'Ramil', 'Rendon', 'Rome', 'Roven',
'Silas', 'Tobias', 'Uriel', 'Zandro', 'Axl', 'Brysen', 'Ced', 'Clarkson',
'Deo', 'Eion', 'Errol', 'Franco', 'Gavin', 'Hansel', 'Isidro', 'Jiro',
'Kiel', 'Loren', 'Matteo', 'Noelito', 'Omar', 'Paxton', 'Quinn', 'Ramon',
'Renz', 'Sandy', 'Tyrone', 'Ulrich', 'Vince', 'Wesley', 'Yvan', 'Zed',
'Alric', 'Brent', 'Caden', 'Dionel', 'Ethaniel', 'Fritz', 'Gerson',
'Hansley', 'Ivar', 'Jeric', 'Kenzo', 'Lex', 'Morris', 'Nate', 'Orville',
'Pio', 'Quentin', 'Rydel', 'Sergio', 'Tobit', 'Ulysses', 'Val', 'Wade',
'Yohan', 'Zyren', 'Adley', 'Cairo', 'Drey', 'Enzo', 'Ferris', 'Gale',
'Hector', 'Iven', 'Jaycee', 'Kaleb', 'Lyndon', 'Macky', 'Nash', 'Oren',
'Pierce', 'Quino', 'Rustin', 'Sylvio', 'Tanner', 'Ulian', 'Vaughn',
'Weston', 'Xeno', 'Yuri', 'Zandro', 'Andro', 'Basil', 'Crisanto', 'Derris',
'Efrain', 'Florenz', 'Gael', 'Hanz', 'Ismael', 'Jeromey', 'Kielan',
'Lucian', 'Marlo', 'Nerio', 'Osric', 'Patrik', 'Rion', 'Santino', 'Timo',
'Vin', 'Wilmer', 'Zaim', 'Zen', 'Gabriel', 'Joshua', 'John', 'Mark', 'James', 'Daniel', 'Matthew', 'Miguel', 'Nathan', 'David',
'Andrew', 'Joseph', 'Christian', 'Emmanuel', 'Adrian', 'Angelo', 'Carl', 'Marco', 'Kenneth', 'Ryan',
'Justin', 'Patrick', 'Paul', 'Francis', 'Anthony', 'Carlos', 'Rafael', 'Samuel', 'Sebastian', 'Elijah',
'Aiden', 'Brent', 'Cedric', 'Darren', 'Ethan', 'Felix',
'Gavin', 'Harold', 'Ian', 'Jacob', 'Kyle', 'Lance',
'Mason', 'Noel', 'Oscar', 'Preston', 'Quentin', 'Riley',
'Steven', 'Tristan', 'Ulysses', 'Vernon', 'Warren', 'Xander',
'Yves', 'Zachary', 'Aaron', 'Benjo', 'Calvin', 'Damien',
'Edward', 'Francis', 'Gerald', 'Harvey', 'Irvin', 'Jasper',
'Kevin', 'Lloyd', 'Marco', 'Nathaniel', 'Owen', 'Patrick',
'Ramon', 'Simon', 'Trevor', 'Vincent', 'Wilfred', 'Zion',
'Alfred', 'Bryan', 'Clarence', 'Daryl', 'Emil', 'Franco',
'Gilbert', 'Henry', 'Isaac', 'Jerome', 'Kristoffer', 'Leandro',
'Mario', 'Noah', 'Paolo', 'Rey', 'Santino', 'Troy',
'Vince', 'Wayne', 'Xian', 'Yohan', 'Zayne', 'Adonis',
'Brandon', 'Cyrus', 'Dominic', 'Enzo', 'Frederick', 'Gideon',
'Hanz', 'Jett', 'Kenzo', 'Luciano', 'Matteo',
'Nico', 'Orion', 'Pierce', 'Rafael', 'Stefan', 'Tobias',
'Valentin', 'Weston', 'Xavi', 'Yasser', 'Zedrick', 'Alonzo',
'Bryce', 'Coby', 'Dexter', 'Eli', 'Finn', 'Gael',
'Hector', 'Ismael', 'Joaquin', 'Keith', 'Lawrence', 'Maverick',
'Nash', 'Oliver', 'Pio', 'Reuben', 'Seth', 'Travis',
'Vaughn', 'Wyatt', 'Yuri', 'Zoren', 'Andrei', 'Benedict',
'Carlo', 'Denver', 'Earl', 'Franz', 'Giovanni', 'Hans',
'Ian', 'Julian', 'Kirk', 'Leo', 'Myles', 'Neo',
'Orlando', 'Philip', 'Rico', 'Sean', 'Thaddeus', 'Vito',
'Wendell', 'Yohan', 'Zayden', 'Adrianne', 'Blaine', 'Cliff',
'Dean', 'Elmer', 'Floyd', 'Gino', 'Hubert', 'Ivan',
'Jonas', 'Kyleen', 'Lemuel', 'Marlon', 'Nolan', 'Omar',
'Patrik', 'Rustin', 'Silas', 'Trent', 'Ulrich', 'Vern',
'Wesley', 'Yancy', 'Zaldy', 'Alaric', 'Blake', 'Chester',
'Dominique', 'Eros', 'Francois', 'Gerry', 'Holden', 'Ira',
'Jules', 'Kean', 'Luther', 'Mackenzie', 'Othello',
'Pax', 'Romeo', 'Samson', 'Tanner', 'Vince', 'Wylie',
'Yago', 'Zionel', 'Alec', 'Ben', 'Dion',
'Emerson', 'Fritz', 'Gareth', 'Hunter', 'Isidro', 'Jairo',
'Kale', 'Levi', 'Miles', 'Oren', 'Paxton',
'Ryder', 'Shawn', 'Theo', 'Urian', 'Victor', 'Wilmer',
'Yosef', 'Zain', 'Alvin', 'Brando', 'Clint', 'Dale',
'Everett', 'Fredrick', 'Garry', 'Howard', 'Isaias', 'Jansen',
'Kaleb', 'Lorenzo', 'Markus', 'Nicko', 'Owen', 'Parker',
'Raymond', 'Shane', 'Tyrone', 'Vince', 'Winston', 'Yusef',
'Zyler', 'Aron', 'Benedicto', 'Chris', 'Dariel', 'Eagan',
'Felipe', 'George', 'Hayden', 'Ivor', 'Justin', 'Kenrick',
'Lian', 'Mack', 'Nolan', 'Osric', 'Pio', 'Ramil',
'Sherwin', 'Tadeo', 'Vaughn', 'Wilbur', 'Yvan', 'Zarek',
'Albie', 'Briggs', 'Casper', 'Damon', 'Eliot', 'Farley',
'Garth', 'Hansel', 'Jayden', 'Kristian', 'Logan',
'Matias', 'Nixon', 'Orin', 'Paulo', 'Reagan', 'Soren',
'Trevin', 'Vernon', 'Wyatt', 'Yul', 'Zebedee', 'Alexei',
'Brock', 'Claudio', 'Derrick', 'Elijah', 'Fidel', 'Gavin',
'Hershel', 'Ismael', 'Jovan', 'Kieran', 'Lucian', 'Marvin',
'Nico', 'Ollie', 'Pablo', 'Roderick', 'Simeon', 'Terrence',
'Uriel', 'Virgil', 'Wayne', 'Yoshua', 'Zain', 'Aries',
'Bruno', 'Caden', 'Darwin', 'Ephraim', 'Finnley', 'Gomer',
'Harry', 'Indie', 'Jesse', 'Keaton', 'Lazaro', 'Mordecai',
'Nero', 'Orvin', 'Presley', 'Rufus', 'Stanley', 'Tomas',
'Uri', 'Vito', 'West', 'Yasir', 'Zev', 'Alton',
'Bernard', 'Carter', 'Dionisio', 'Edison', 'Fernando', 'Gabe',
'Hugh', 'Immanuel', 'Joel', 'Kristoff', 'Lucio', 'Mikel',
'Nevin', 'Osmond', 'Paulino', 'Rico', 'Stewart', 'Trent',
'Ulysses', 'Vince', 'Wylder', 'Yunus', 'Zarek', 'Abel',
'Benson', 'Claudio', 'Dennis', 'Ezekiel', 'Francis', 'Gavin',
'Harlan', 'Ivan', 'Jericho', 'Kendrick', 'Lars', 'Mathew',
'Nestor', 'Octavio', 'Perry', 'Rogelio', 'Sandy', 'Tyrone',
'Ulises', 'Vern', 'Wendel', 'Yves', 'Zac', 'Albert',
'Blair', 'Cruz', 'Dionel', 'Elvin', 'Fabian', 'Giancarlo',
'Hanzel', 'Iago', 'Jon', 'Kyle', 'Leif', 'Marcelo',
'Nigel', 'Orwell', 'Pierce', 'Roldan', 'Sage', 'Truman',
'Urbano', 'Vance', 'Wes', 'Yuki', 'Zandro', 'Amiel',
'Bert', 'Colin', 'Daryl', 'Erwin', 'Francisco', 'Geoff',
'Harris', 'Ian', 'Jayvee', 'Kristo', 'Logen', 'Manny',
'Nuel', 'Olan', 'Pablo', 'Riel', 'Simeon', 'Thane',
'Umar', 'Val', 'Wyler', 'Yarden', 'Zeke', 'Anton',
'Bryce', 'Caden', 'Devon', 'Eman', 'Fritz', 'Garry',
'Henri', 'Isagani', 'Jiro', 'Kael', 'Lauro', 'Mackie',
'Nash', 'Ogie', 'Pax', 'Roi', 'Stefano', 'Troy',
'Uno', 'Vaughn', 'Wayne', 'Yasir', 'Zaniel', 'Armand',
'Blas', 'Corbin', 'Dindo', 'Edric', 'Fermin', 'Gerry',
'Hendrick', 'Isidore', 'Jemuel', 'Kurt', 'Lemuel', 'Maurice',
'Natan', 'Olan', 'Paulo', 'Renz', 'Sandy', 'Tobit',
'Uriel', 'Vito', 'Weston', 'Yuri', 'Zander', 'Ariel',
'Benny', 'Carmelo', 'Darel', 'Earl', 'Flint', 'Gian',
'Henley', 'Jeff', 'Kiko', 'Louie', 'Marlon',
'Nash', 'Orion', 'Pietro', 'Rico', 'Stevan', 'Tomas',
'Ulric', 'Vernon', 'Wyatt', 'Yeshua', 'Zeb', 'Axel',
'Berto', 'Clyde', 'Darrel', 'Ely', 'Fredo', 'Gelo',
'Hector', 'Irving', 'Jomar', 'Ken', 'Lenny', 'Mico', 'Nashon', 'Owen', 'Pietro', 'Randel', 'Sergio', 'Tristan',
'Uziel', 'Vaughn', 'Warren', 'Yvan', 'Zain', 'Alaric',
'Briggs', 'Cyril', 'Drew', 'Evan', 'Floyd', 'Gareth',
'Hiro', 'Ismael', 'Jaden', 'Kurtis', 'Leandro', 'Miguelito',
'Nolan', 'Osmar', 'Paxton', 'Ronan', 'Soren', 'Trey',
'Ulises', 'Vann', 'Wilbert', 'Yuri', 'Zandro', 'Aiden',
'Brando', 'Carter', 'Dustin', 'Elian', 'Fermin', 'Gavin',
'Hudson', 'Isagani', 'Jonel', 'Kasey', 'Lyle', 'Marlon',
'Noel', 'Omar', 'Preston', 'Rufino', 'Santino', 'Toby',
'Uri', 'Val', 'Wade', 'Yeshua', 'Zed', 'Alvin',
'Bryant', 'Colby', 'Dante', 'Eliot', 'Franco', 'Gideon',
'Hershel', 'Isaiah', 'Jasper', 'Kenric', 'Luther', 'Marcus',
'Nathaniel', 'Orvin', 'Pio', 'Rodel', 'Simeon', 'Tanner',
'Urbano', 'Victor', 'Wyatt', 'Yancey', 'Zavier', 'Arnold',
'Blake', 'Chester', 'Diego', 'Evan', 'Felipe', 'Grayson',
'Hendrick', 'Ian', 'Jiro', 'Karlo', 'Luis', 'Matthias',
'Nestor', 'Odie', 'Paco', 'Ronaldo', 'Salvador', 'Tyrone',
'Ulric', 'Vincent', 'Wendell', 'Yusef', 'Zeke', 'Anderson',
'Bruce', 'Clark', 'Davin', 'Eugene', 'Felix', 'Gustavo',
'Hiram', 'Irvin', 'Julius', 'Karl', 'Leopoldo', 'Morgan',
'Nixon', 'Oberon', 'Percy', 'Roland', 'Sam', 'Travis',
'Uziel', 'Vern', 'Willard', 'Yuri', 'Zacharias', 'Arturo',
'Bryan', 'Coby', 'Dennis', 'Edison', 'Frank', 'Gilbert',
'Harry', 'Isaias', 'Jose', 'Kendrick', 'Lance', 'Marcel',
'Nilo', 'Owen', 'Patrick', 'Rico', 'Sean', 'Theo',
'Uriah', 'Vince', 'Walter', 'Yohan', 'Zachary', 'Amos',
'Bobby', 'Curtis', 'Dion', 'Elias', 'Fritz', 'Gerry',
'Hansel', 'Ivan', 'Jorge', 'Kiel', 'Leo', 'Manny',
'Niel', 'Oscar', 'Paul', 'Randy', 'Seth', 'Trent',
'Ulrich', 'Victor', 'Wesley', 'Yvan', 'Zane', 'Ariel',
'Benji', 'Chris', 'Domingo', 'Edwin', 'Freddie', 'Gino',
'Harvey', 'Irwin', 'Joel', 'Kirk', 'Lou', 'Martin',
'Noel', 'Ollie', 'Phillip', 'Randy', 'Samson', 'Timothy',
'Ulysses', 'Vaughn', 'Winston', 'Yves', 'Zion', 'Adriel',
'Benedict', 'Connor', 'Dionel', 'Emmanuel', 'Francis', 'Gerson',
'Hugh', 'Isidro', 'Joshua', 'Kean', 'Lemuel', 'Miguel',
'Neil', 'Omar', 'Paolo', 'Rainer', 'Simeon', 'Tadeo',
'Urbano', 'Vincent', 'Wendell', 'Yul', 'Zandro', 'Alexis',
'Brent', 'Clint', 'Dario', 'Edison', 'Felipe', 'Gareth',
'Humbert', 'Isidro', 'Jericho', 'Kiefer', 'Levi', 'Maverick',
'Nick', 'Orville', 'Pierre', 'Rufus', 'Stefano', 'Troy',
'Uziel', 'Val', 'Warren', 'Yancy', 'Zeke', 'Albert',
'Benny', 'Carmelo', 'Dindo', 'Elvin', 'Franco', 'Giovanni',
'Henri', 'Ivan', 'Jairus', 'Kaleb', 'Lucio', 'Maurice',
'Nathan', 'Orion', 'Paolo', 'Ruel', 'Santino', 'Thaddeus',
'Uri', 'Vince', 'Wyatt', 'Yvan', 'Zionel', 'Anton',
'Bryce', 'Cedric', 'Darrel', 'Eren', 'Fabian', 'Gelo',
'Hans', 'Isidro', 'Jonel', 'Kiko', 'Lars', 'Mico',
'Noel', 'Olan', 'Patrick', 'Rico', 'Stephen', 'Tristan',
'Uly', 'Vaughn', 'Wendell', 'Yeshua', 'Zadok', 'Alaric',
'Brad', 'Clyde', 'Dylan', 'Eugene', 'Fermin', 'Garry',
'Hendrick', 'Isaac', 'Julian', 'Kenneth', 'Lorenzo', 'Marco',
'Noah', 'Oren', 'Paco', 'Rian', 'Silas', 'Tommy',
'Urbie', 'Vince', 'Walter', 'Yvan', 'Zayden', 'Amiel',
'Blas', 'Colin', 'Darwin', 'Ernest', 'Felix', 'Gabe',
'Harris', 'Ian', 'Jerome', 'Kevin', 'Lyle', 'Matthew',
'Nico', 'Owen', 'Paul', 'Ramon', 'Simon', 'Trent',
'Uriel', 'Victor', 'Will', 'Yves', 'Zander', 'Arvin',
'Bryan', 'Cedrick', 'Dale', 'Elias', 'Fred', 'George',
'Hugh', 'Isaac', 'Jude', 'Karlo', 'Lance', 'Miguel',
'Nash', 'Oscar', 'Patrick', 'Ralph', 'Steven', 'Tyler',
'Urbano', 'Vince', 'Wes', 'Yuri', 'Zack', 'Aiden',
'Blake', 'Connor', 'Daryl', 'Eren', 'Franz', 'Gideon',
'Hansel', 'Ivan', 'Jonas', 'Kean', 'Levi', 'Morris',
'Niel', 'Omar', 'Paulo', 'Ricky', 'Seth', 'Tristan',
'Ulysses', 'Vaughn', 'Wyatt', 'Yohan', 'Zain', 'Aaron',
'Brett', 'Clark', 'Darren', 'Eugene', 'Felix', 'Gabriel',
'Henry', 'Isaiah', 'Jacob', 'Kyle', 'Logan', 'Martin',
'Nolan', 'Owen', 'Pierce', 'Roderick', 'Shawn', 'Troy',
'Ulric', 'Vernon', 'Wayne', 'Yves', 'Zach', 'Ariel',
'Bryce', 'Cliff', 'Dean', 'Eli', 'Francis', 'Gio',
'Harry', 'Ivan', 'Jett', 'Ken', 'Liam', 'Matthew',
'Noel', 'Omar', 'Parker', 'Rafael', 'Simon', 'Theo',
'Ulysses', 'Victor', 'Wesley', 'Yuri', 'Zane', 'Andre',
'Brent', 'Cyrus', 'Dion', 'Eden', 'Frank', 'Gabe',
'Hans', 'Isaac', 'Joel', 'Kyle', 'Lance', 'Mark',
'Nico', 'Oscar', 'Paul', 'Ryan', 'Seth', 'Trent',
'Urbano', 'Vince', 'Walter', 'Yvan', 'Zeke', 'Aiden',
'Blair', 'Clifford', 'Dionisio', 'Eliot', 'Franco', 'Gavin',
'Hendrick', 'Isidro', 'Jules', 'Kenji', 'Lucio', 'Marcus',
'Noel', 'Ollie', 'Pierce', 'Rico', 'Stefan', 'Tobias',
'Uriah', 'Vaughn', 'Wyatt', 'Yves', 'Zion', 'Jerome', 'Jayden', 'Daniel', 'Ezekiel', 'Russell', 'Francis', 'Erwin', 'Kenneth', 'Ramon', 'Leo', 'Brylle', 'Philip', 'Leandro', 'Gerald', 'Jonathan', 'Timothy', 'Earl', 'Harold', 'Mark', 'Ryan', 'Kevin', 'Romeo', 'Dominic', 'Marvin', 'Alexander', 'Joel', 'Ralph', 'Allan', 'Kian', 'Simon', 'James', 'Alfred', 'Thomas', 'Paolo', 'John', 'Elijah', 'Rene', 'Martin', 'Justin', 'Patrick', 'Lloyd', 'Jose', 'Allen', 'Jonathan', 'Ronald', 'Jeremiah', 'Rafael', 'Christopher', 'Rowell', 'Kurt', 'Angelo', 'Leonard', 'Jason', 'Reymond', 'Kenzo', 'Elric', 'Samuel', 'Nelson', 'Aiden', 'Kian', 'Ramon', 'Kurt', 'Alexander', 'Rome', 'Martin', 'Zachary', 'Erwin', 'Gabriel', 'Christian', 'Adrian', 'Zion', 'Sean', 'Miguel', 'Jayden', 'Renz', 'Ian', 'Arnold', 'Carlo', 'Gerald', 'Jared', 'Edgar', 'Tony', 'Kevin', 'Carl', 'Paolo', 'Earl', 'Clyde', 'Brylle', 'Kian', 'Robert', 'Nelson', 'Martin', 'Sean', 'Arthur', 'Roderick', 'Marvin', 'Kenneth', 'Leandro', 'Tony', 'Jacob', 'Miguel', 'Rome', 'Carlo', 'Arvin', 'Axel', 'Noel', 'Zane', 'Ramon', 'Daryl', 'Russell', 'Darren', 'Roland', 'Rafael', 'Joshua', 'Aaron', 'Paolo', 'Eugene', 'Arvin', 'Jason', 'Jared', 'Lance', 'Aiden', 'Daryl', 'Joshua', 'Lawrence', 'Jose', 'Ramon', 'Noah', 'Victor', 'Gerald', 'Alvin', 'Jeffrey', 'Kurt', 'Roland', 'Carlo', 'Harvey', 'Reymond', 'Allen', 'Victor', 'Adrian', 'Justin', 'Allan', 'Axel', 'Albert', 'Santino', 'Ferdinand', 'Jayden', 'Dominic', 'Vincent', 'Xander', 'Dennis', 'Kenzo', 'Edgar', 'Paolo', 'Leonard', 'Edward', 'Ralph', 'Allen', 'Mathew', 'Lance', 'Christian', 'Dominic', 'Nathan', 'Jonathan', 'Zachary', 'Gilbert', 'Ferdinand', 'Alonzo', 'Joel', 'Mark', 'Timothy', 'Anthony', 'Dean', 'Allen', 'Carl',
'Reginald', 'Valentino', 'Weston', 'Xavier', 'Zachariah', 'Adriel',
'Benedict', 'Constantine', 'Dashiell', 'Emmanuel', 'Francisco', 'Giovanni',
'Harrison', 'Ignatius', 'Jeremiah', 'Kingston', 'Leonardo', 'Montgomery',
'Nathaniel', 'Orlando', 'Princeton', 'Remington',
'Afton', 'Finley', 'Kearney', 'Keary', 'Kegan', 'Keir', 'Kendall', 'Mannix',
'Melvin', 'Merlin', 'Murray', 'Perth', 'Ronan', 'Sean',
'Tadc', 'Tegan', 'Tiernan', 'Torin', 'Vaughan',
'Hodding', 'Kyler', 'Maarten', 'Rembrandt', 'Rodolf', 'Roosevelt',
'Schuyler', 'Van', 'Vandyke', 'Wagner',
'Aldo', 'Aleyn', 'Alford', 'Anson', 'Archibald',
'Atley', 'Atwell', 'Audie', 'Avery', 'Ayers', 'Baker', 'Balder',
'Barker', 'Bayard', 'Bishop', 'Blake', 'Blaine', 'Bramwell',
'Brant', 'Bryce', 'Byron',
'Cage', 'Cedar', 'Churchill', 'Colton', 'Crandall',
'Dack', 'Dakin', 'Dallin', 'Dalton', 'Dartmouth', 'Dawson', 'Dax',
'Denton', 'Denver', 'Denzel', 'Diamond',
'Doane', 'Doc', 'Draper', 'Dugan', 'Dunley',
'Dunn', 'Dunstan', 'Dwyer', 'Dyson', 'Edison',
'Edred', 'Egbert', 'Eldwin', 'Elgin', 'Ellis',
'Elwood', 'Emmett', 'Errol', 'Everest', 'Ewing', 'Falkner',
'Farold', 'Farran', 'Fenton', 'Finch', 'Fitz', 'Fleming',
'Flint', 'Fox', 'Freedom', 'Gaines',
'Gale', 'Gallant', 'Garfield', 'Garrett', 'Geary',
'Gene', 'Gifford', 'Gomer', 'Graham',
'Green', 'Griffin', 'Grover',
'Hart', 'Haskel', 'Heathcliff', 'Heaton', 'Helmut', 'Houston',
'Howard', 'Howe', 'Hoyt', 'Hurst', 'Huxley', 'Indiana',
'Jagger', 'Jarrell', 'Jax', 'Jaxon', 'Jay',
'Jet', 'Judson', 'Julian', 'Kaid', 'Keane', 'Keaton',
'Kell', 'Kelsey', 'Kelvin', 'Kennard', 'Kenneth', 'Kentlee',
'Ker', 'Kester', 'Kingsley', 'Kirby', 'Klay',
'Knightley', 'Kody', 'Kolby', 'Kolton', 'Kyler',
'Lake', 'Langston', 'Lathrop', 'Leighton',
'Lex', 'Lindell', 'Lindsay', 'Livingston', 'Locke', 'London',
'Lord', 'Lowell', 'Ludlow', 'Luke', 'Lusk', 'Lyndal',
'Lynn', 'Maddox', 'Mander',
'Mansfield', 'Markham', 'Marley', 'Marsh',
'Marston', 'Martin', 'Marvin', 'Massey', 'Matheson', 'Maverick',
'Maxwell', 'Mayer', 'Meldon',
'Merrick', 'Merton', 'Miles', 'Monte', 'Montgomery',
'Moreland', 'Morley', 'Morrison', 'Myles', 'Ned',
'Newt', 'Nile', 'Norman',
'Norris', 'Norton', 'Norvin',
'Norwin', 'Odell',
'Orlan', 'Ormond', 'Orrick', 'Orson', 'Osborn',
'Osgood', 'Ossie', 'Overton', 'Parsifal',
'Peers', 'Pelton', 'Pierce', 'Piers',
'Powell', 'Radford', 'Radley',
'Randal', 'Reed', 'Reynold',
'Rhett', 'Rhodes', 'Richard', 'Ridge', 'Ridgley',
'Rivers', 'Roan', 'Robin', 'Robson', 'Rockwell',
'Roden', 'Roe', 'Roldan', 'Ross',
'Rowley', 'Royce', 'Rudd', 'Rune',
'Ryder', 'Sage', 'Salisbury', 'Sanborn',
'Saxon', 'Searles', 'Seaton',
'Seger', 'Selby', 'Seldon', 'Selwyn', 'Seton',
'Sewell', 'Shade', 'Shelby', 'Sheldon', 'Shepley',
'Sidwell', 'Simeon', 'Siward', 'Skye',
'Slate', 'Smith', 'Somerton',
'Spalding', 'Stafford', 'Stanbury',
'Stanwick', 'Starr', 'Steadman', 'Sterling', 'Stetson', 'Stiles',
'Stoke', 'Storm', 'Stuart', 'Sunny', 'Sydney',
'Sylvester', 'Taft', 'Talon', 'Templeton', 'Thompson',
'Thorley', 'Tolbert', 'Tyson', 'Udall',
'Ulmer', 'Upjohn', 'Upton', 'Usher', 'Uther', 'Vail',
'Valen', 'Vine', 'Vinson', 'Vinton',
'Wadell', 'Wadsworth', 'Wain',
'Waite', 'Walcott', 'Wales', 'Walford', 'Walker',
'Waller', 'Walsh', 'Walworth', 'Warburton',
'Ward', 'Wardley', 'Ware', 'Waring',
'Warley', 'Warrick', 'Warton', 'Warwick', 'Washburn', 'Wat',
'Wayde', 'Waylon', 'Webb', 'Weldon',
'Westbrook', 'Whitby', 'Whitcomb', 'Whittaker',
'Wiley', 'Wilford', 'Wilton', 'Wirt',
'Wisdom', 'Witton', 'Wolcott', 'Wolf', 'Wolfe',
'Woodson', 'Wythe', 'Yardley', 'Yule', 'Zani',
]

first_names_female = [
'Maria', 'Ana', 'Sofia', 'Isabella', 'Gabriela', 'Valentina', 'Camila',
'Angelica', 'Nicole', 'Michelle', 'Christine', 'Sarah', 'Jessica',
'Andrea', 'Patricia', 'Jennifer', 'Karen', 'Ashley', 'Jasmine', 'Princess',
'Angel', 'Joyce', 'Kristine', 'Diane', 'Joanna', 'Carmela', 'Isabel',
'Lucia', 'Elena',
'Abigail', 'Adeline', 'Adrienne', 'Agnes', 'Aileen', 'Aira', 'Aiza',
'Alana', 'Alexa', 'Alexis', 'Alice', 'Allyson', 'Alyssa', 'Amara',
'Amelia', 'Amirah', 'Anabelle', 'Anastasia', 'Andrea', 'Angela', 'Angelie',
'Angelyn', 'Anita', 'Annabelle', 'Anne', 'Annie', 'Antoinette', 'April',
'Ariana', 'Arlene', 'Aubrey', 'Audrey', 'Aurora', 'Ava', 'Bea', 'Bella',
'Bernadette', 'Bianca', 'Blessy', 'Brianna', 'Bridget', 'Carla', 'Carmel',
'Cassandra', 'Catherine', 'Cecilia', 'Celeste', 'Charisse', 'Charlene',
'Charlotte', 'Chelsea', 'Cherry', 'Cheska', 'Clarice', 'Claudia', 'Coleen',
'Colleen', 'Cristina', 'Cynthia', 'Dahlia', 'Danica', 'Daniela',
'Danielle', 'Darlene', 'Diana', 'Dominique', 'Donna', 'Dorothy', 'Eden',
'Elaine', 'Eleanor', 'Elisa', 'Eliza', 'Ella', 'Ellen', 'Eloisa', 'Elsa',
'Emerald', 'Emily', 'Emma', 'Erica', 'Erin', 'Esme', 'Eunice', 'Faith',
'Fatima', 'Felice', 'Flor', 'Frances', 'Francesca', 'Genevieve', 'Georgia',
'Gillian', 'Giselle', 'Glenda', 'Grace', 'Gretchen', 'Gwen', 'Hailey',
'Hannah', 'Hazel', 'Heather', 'Heidi', 'Helen', 'Helena', 'Hope', 'Iana',
'Irene', 'Irish', 'Isabelle', 'Ivana', 'Ivory', 'Jacqueline', 'Jamie',
'Jane', 'Janella', 'Janet', 'Janine', 'Janna', 'Jasmine', 'Jean',
'Jeanine', 'Jem', 'Jenica', 'Jessa', 'Jillian', 'Joan', 'Joanna', 'Joanne',
'Jocelyn', 'Jolina', 'Joy', 'Judith', 'Julia', 'Julianne', 'Juliet',
'Justine', 'Kaila', 'Kaitlyn', 'Karen', 'Karina', 'Kate', 'Katrina',
'Kayla', 'Keira', 'Kendra', 'Kim', 'Kimberly', 'Krisha', 'Krista',
'Krystel', 'Kyla', 'Kylie', 'Lara', 'Larissa', 'Laura', 'Lauren', 'Lea',
'Leanne', 'Lena', 'Leslie', 'Lexi', 'Lianne', 'Liza', 'Lorraine', 'Louisa',
'Louise', 'Lovely', 'Lucille', 'Luna', 'Lyndsay', 'Lyra', 'Mae', 'Maggie',
'Maja', 'Mandy', 'Marcia', 'Margaret', 'Marian', 'Mariel', 'Marilyn',
'Marina', 'Marissa', 'Marites', 'Martha', 'Mary', 'Matilda', 'Maureen',
'Maxine', 'May', 'Megan', 'Melissa', 'Mia', 'Mika', 'Mikayla', 'Mila',
'Mira', 'Miranda', 'Mirella', 'Monica', 'Nadia', 'Naomi', 'Natalie',
'Nathalie', 'Nerissa', 'Nika', 'Nina', 'Nora', 'Norma', 'Olivia',
'Ophelia', 'Pamela', 'Patricia', 'Paula', 'Pauline', 'Pearl', 'Phoebe',
'Pia', 'Precious', 'Queenie', 'Quiana', 'Rachelle', 'Rae', 'Rain', 'Raisa',
'Ramona', 'Raven', 'Reina', 'Rhea', 'Rica', 'Richelle', 'Rina', 'Rochelle',
'Rosa', 'Rosalie', 'Roseanne', 'Rowena', 'Ruth', 'Sabrina', 'Samantha',
'Samira', 'Sandra', 'Sara', 'Selene', 'Serena', 'Shaira', 'Shaina',
'Shanelle', 'Shanika', 'Sharon', 'Sheena', 'Sheila', 'Sherlyn', 'Shiela',
'Shirley', 'Siena', 'Sierra', 'Sofia', 'Sophia', 'Steffany', 'Stephanie',
'Summer', 'Susan', 'Suzette', 'Sylvia', 'Tanya', 'Tara', 'Tatiana',
'Tessa', 'Thea', 'Theresa', 'Trisha', 'Trista', 'Valeria', 'Vanessa',
'Veronica', 'Vicky', 'Victoria', 'Viel', 'Vina', 'Vivian', 'Wendy',
'Whitney', 'Yasmin', 'Ysabel', 'Yvette', 'Yvonne', 'Zara', 'Zelda', 'Zia',
'Zoe', 'Althea', 'Arya', 'Beatriz', 'Czarina', 'Dayanara', 'Elora',
'Fiona', 'Gianna', 'Helena', 'Indira', 'Janine', 'Kalista', 'Larraine',
'Maeve', 'Noelle', 'Odessa', 'Patrina', 'Rowan', 'Selina', 'Tahlia', 'Una',
'Vienna', 'Willow', 'Xandra', 'Yanna', 'Zyra', 'Clarissa', 'Diane',
'Fritzie', 'Harley', 'Ivette', 'Juliana', 'Karmina', 'Leira', 'Maricel',
'Nerina', 'Odette', 'Pia', 'Riona', 'Sandy', 'Tanya', 'Vielka', 'Winona',
'Xyla', 'Ysa', 'Zian', 'Adria', 'Aubriel', 'Celina', 'Devina', 'Emerie',
'Florence', 'Graciela', 'Hilary', 'Isla', 'Jaira', 'Kelsey', 'Lianne',
'Maika', 'Nashira', 'Orla', 'Perla', 'Quinley', 'Roxanne', 'Soleil',
'Therese', 'Ulani', 'Verona', 'Xaviera', 'Althea', 'Andrea', 'Angela', 'Anna', 'Sarah', 'Nicole', 'Ella', 'Sophia', 'Isabella',
'Jasmine', 'Kristine', 'Michelle', 'Patricia', 'Catherine', 'Victoria', 'Samantha', 'Ashley', 'Gabrielle', 'Maryanne',
'Christine', 'Angelica', 'Stephanie', 'Jennifer', 'Amanda', 'Diana', 'Clarissa', 'Erica', 'Theresa', 'Monica',
'Ariana', 'Bea', 'Camille', 'Danica', 'Elaine', 'Faith',
'Giselle', 'Hannah', 'Inara', 'Janelle', 'Kaila', 'Lianne',
'Monique', 'Nadine', 'Olivia', 'Phoebe', 'Queenie', 'Rachelle',
'Savannah', 'Tiffany', 'Uma', 'Venice', 'Wynona', 'Ysabelle',
'Zoey', 'Abigail', 'Bianca', 'Caitlyn', 'Dahlia', 'Eliza',
'Farrah', 'Georgia', 'Hailey', 'Ivy', 'Jasmine', 'Katrina',
'Lara', 'Maxine', 'Nathalie', 'Opal', 'Patricia', 'Renee',
'Sienna', 'Trisha', 'Vania', 'Willow', 'Yasmin', 'Zaira',
'Alaina', 'Bridget', 'Clarisse', 'Deborah', 'Erika', 'Fiona',
'Gemma', 'Hazel', 'Isla', 'Janine', 'Kayla', 'Lianne',
'Mikaela', 'Noreen', 'Odessa', 'Penelope', 'Quiana', 'Rafaela',
'Sabrina', 'Therese', 'Valerie', 'Whitney', 'Yvette', 'Zelda',
'Alessia', 'Bethany', 'Cassandra', 'Diana', 'Elyse', 'Freya',
'Grace', 'Harriet', 'Iana', 'Jessa', 'Kimberly', 'Lynette',
'Marielle', 'Noemi', 'Orla', 'Patrice', 'Rosalind', 'Sophia',
'Tamara', 'Veronica', 'Willa', 'Yara', 'Zion', 'Amara',
'Bernadette', 'Celine', 'Delaney', 'Estelle', 'Faye', 'Gianna',
'Hilary', 'Ivana', 'Jillian', 'Keziah', 'Larissa', 'Mara',
'Nika', 'Oriana', 'Pamela', 'Rianne', 'Selene', 'Talia',
'Vittoria', 'Wendy', 'Ysadora', 'Zia', 'Aubrey', 'Blythe',
'Carmela', 'Daphne', 'Eden', 'Florence', 'Gwen', 'Helena',
'Inez', 'Joanna', 'Keira', 'Lourdes', 'Mayumi', 'Nadine',
'Ondrea', 'Pauleen', 'Regina', 'Simone', 'Theresa', 'Vera',
'Wynne', 'Yumi', 'Zandra', 'Aimee', 'Brooklyn', 'Carla',
'Daria', 'Eloisa', 'Fritzie', 'Glenda', 'Haidee', 'Isabel',
'Juliana', 'Kirsten', 'Liana', 'Matilda', 'Noreen', 'Ophelia',
'Patty', 'Rina', 'Samantha', 'Trina', 'Vienna', 'Xyra',
'Ynah', 'Zyra', 'Alana', 'Bettina', 'Clarissa', 'Darlene',
'Evelyn', 'Faith', 'Giulia', 'Hana', 'Ivory', 'Jamie',
'Krista', 'Lianne', 'Macy', 'Nerissa', 'Odette', 'Pauline',
'Rhianna', 'Selina', 'Trixie', 'Verna', 'Willa', 'Yara',
'Zenia', 'Angelie', 'Brianna', 'Catrina', 'Denise', 'Ellaine',
'Fiona', 'Grace', 'Hillary', 'Imogen', 'Janice', 'Kiara',
'Lara', 'Marin', 'Nina', 'Odessa', 'Phoebe', 'Reina',
'Savina', 'Tanya', 'Vanna', 'Wendelyn', 'Yvette', 'Zaira',
'Arielle', 'Blanca', 'Cheska', 'Doreen', 'Emeraude', 'Francine',
'Gillian', 'Harley', 'Isha', 'Jasmine', 'Krizia', 'Laraine',
'Misha', 'Nashira', 'Olesya', 'Patrizia', 'Rachelle', 'Serena',
'Tracy', 'Vanessa', 'Wynette', 'Ysabel', 'Zoe', 'Alliah',
'Beatriz', 'Caren', 'Danielle', 'Elora', 'Fatima', 'Gina',
'Hazel', 'Isabelle', 'Jade', 'Katya', 'Liza', 'Margaux',
'Nina', 'Odette', 'Pia', 'Raquel', 'Sofia', 'Therese',
'Vivienne', 'Winter', 'Ynah', 'Zia', 'Aaliyah', 'Blaire',
'Czarina', 'Desiree', 'Eliza', 'Faith', 'Georgina', 'Heidi',
'Ingrid', 'Jemima', 'Kailyn', 'Layla', 'Mika', 'Nicole',
'Olive', 'Paola', 'Ruth', 'Selena', 'Tala', 'Valeria',
'Xandra', 'Ysabella', 'Zyrah', 'Amira', 'Bettina', 'Chantal',
'Diane', 'Eira', 'Fiona', 'Gretchen', 'Hana', 'Ina',
'Janelle', 'Kendra', 'Lani', 'Mara', 'Nadine', 'Orla',
'Pauleen', 'Rafaela', 'Sandy', 'Tina', 'Verna', 'Winnie',
'Ysa', 'Zara', 'Ariane', 'Bambi', 'Caitlin', 'Danna',
'Ella', 'Faith', 'Gabbie', 'Hellen', 'Inna', 'Jessamine',
'Kyla', 'Lara', 'Mikaela', 'Noreen', 'Oona', 'Penelope',
'Raina', 'Sophia', 'Theresa', 'Vina', 'Winter', 'Yumi',
'Zelene', 'Alyssa', 'Briar', 'Chesca', 'Danna', 'Erin',
'Faye', 'Gwyneth', 'Hannah', 'Ira', 'Jodie', 'Keira',
'Luna', 'Mariel', 'Nika', 'Olivia', 'Paula', 'Rachelle',
'Sienna', 'Tessa', 'Vera', 'Wynne', 'Yelena', 'Zaira',
'Annika', 'Bea', 'Corinne', 'Dahlia', 'Elara', 'Fritzie',
'Giselle', 'Hailey', 'Isla', 'Jamie', 'Kassandra', 'Lyra',
'Mira', 'Nadine', 'Ornella', 'Patrice', 'Quinn', 'Renee',
'Sabrina', 'Trixie', 'Valentina', 'Winnie', 'Ysabel', 'Zia',
'Abbie', 'Blanche', 'Cleo', 'Daisy', 'Eleni', 'Faith',
'Gretel', 'Helena', 'Ivana', 'Joyce', 'Kara', 'Lianne',
'Maeve', 'Nina', 'Oriana', 'Pia', 'Ruth', 'Sari',
'Tanya', 'Vivian', 'Wynona', 'Yanna', 'Zenya', 'Asha',
'Brielle', 'Carmina', 'Dina', 'Elaiza', 'Florence', 'Gia',
'Hazel', 'Isabel', 'Jasmin', 'Kristine', 'Lia', 'Marla',
'Nadine', 'Odette', 'Patty', 'Raquel', 'Samara', 'Tessa',
'Vicky', 'Winona', 'Yani', 'Zyra', 'Aileen', 'Briena', 'Carla', 'Dayanara', 'Evelina', 'Fiona',
'Gwen', 'Hazel', 'Isobel', 'Jenna', 'Kaila', 'Leona',
'Meg', 'Nadine', 'Odessa', 'Pamela', 'Queenie', 'Renee',
'Savina', 'Trisha', 'Valeria', 'Wynnie', 'Yuna', 'Zelia',
'Althea', 'Blaine', 'Celina', 'Delia', 'Ember', 'Francesca',
'Gianna', 'Helene', 'Ingrid', 'Jordyn', 'Kyla', 'Lyn',
'Mikhaela', 'Nella', 'Orla', 'Penelope', 'Renee', 'Sophia',
'Tamara', 'Vanna', 'Willow', 'Yvaine', 'Zinnia', 'Aimee',
'Bella', 'Clarisse', 'Daria', 'Ellaine', 'Faith', 'Grace',
'Hannah', 'Ivy', 'Jazmine', 'Krisha', 'Laraine', 'Marina',
'Nia', 'Odelle', 'Priscilla', 'Rhianna', 'Sierra', 'Tanya',
'Vanessa', 'Wren', 'Ysadora', 'Zoe', 'Ariella', 'Bianca',
'Cailin', 'Daniella', 'Eunice', 'Felicia', 'Gabrielle', 'Hillary',
'Isabela', 'Jemma', 'Kianna', 'Lianne', 'Mayumi', 'Noelle',
'Olivine', 'Patricia', 'Roselyn', 'Tala', 'Veronica', 'Wendy',
'Yen', 'Zandra', 'Alethea', 'Brynn', 'Catrina', 'Dianne',
]

surnames = [
'Reyes', 'Santos', 'Cruz', 'Bautista', 'Garcia', 'Flores', 'Gonzales',
'Martinez', 'Ramos', 'Mendoza', 'Rivera', 'Torres', 'Fernandez', 'Lopez',
'Castillo', 'Aquino', 'Villanueva', 'Santiago', 'Dela Cruz', 'Perez',
'Castro', 'Mercado', 'Domingo', 'Gutierrez', 'Ramirez', 'Valdez',
'Alvarez', 'Salazar', 'Morales', 'Navarro', 'Abad', 'Abella', 'Abellanosa',
'Acevedo', 'Aguinaldo', 'Aguilar', 'Alcantara', 'Almonte', 'Alonzo',
'Altamirano', 'Amador', 'Amparo', 'Ancheta', 'Andrada', 'Angeles',
'Antonio', 'Aquino', 'Araneta', 'Arceo', 'Arellano', 'Arias', 'Asuncion',
'Avila', 'Ayala', 'Bagasbas', 'Balagtas', 'Balane', 'Balbuena',
'Ballesteros', 'Baltazar', 'Banaga', 'Bao', 'Barcenas', 'Baron', 'Basa',
'Basco', 'Bautista', 'Beltran', 'Benitez', 'Bernal', 'Blanco', 'Borja',
'Briones', 'Buendia', 'Bustamante', 'Caballero', 'Cabanilla', 'Cabrera',
'Cadiz', 'Calderon', 'Camacho', 'Canlas', 'Capili', 'Carpio', 'Castaneda',
'Castroverde', 'Catapang', 'Celis', 'Ceniza', 'Cerda', 'Chavez',
'Clemente', 'Coloma', 'Concepcion', 'Cordova', 'Cornejo', 'Coronel',
'Corpuz', 'Cortez', 'Cruzado', 'Cuenca', 'Cuevas', 'Dacanay', 'Daguio',
'Dalisay', 'Daluz', 'Damaso', 'Dancel', 'Danganan', 'De Guzman',
'Del Mundo', 'Del Rosario', 'Delos Reyes', 'Deluna', 'Desamparado',
'Dimaandal', 'Dimaculangan', 'Dizon', 'Dolor', 'Duque', 'Ebarle',
'Echevarria', 'Elizalde', 'Encarnacion', 'Enriquez', 'Escalante',
'Escobar', 'Escueta', 'Espinosa', 'Espiritu', 'Estrella', 'Evangelista',
'Fabian', 'Fajardo', 'Falcon', 'Fernan', 'Ferrolino', 'Ferrer', 'Figueras',
'Florencio', 'Fonseca', 'Francisco', 'Fuentes', 'Galang', 'Galvez',
'Garay', 'Garing', 'Gaspar', 'Gavino', 'Giron', 'Godinez', 'Gomez',
'Gonzaga', 'Granado', 'Guerrero', 'Guevarra', 'Guinto', 'Hernandez',
'Herrera', 'Hilario', 'Ignacio', 'Ilagan', 'Inocencio', 'Intal', 'Isidro',
'Jacinto', 'Javier', 'Jimenez', 'Labao', 'Lacson', 'Ladines', 'Lagman',
'Lao', 'Lara', 'Lasala', 'Lazaro', 'Legaspi', 'Leones', 'Leviste',
'Liwanag', 'Lorenzo', 'Lucero', 'Lumibao', 'Luna', 'Macaraig', 'Madarang',
'Madrid', 'Magalong', 'Magbago', 'Magno', 'Magpantay', 'Malabanan',
'Malig', 'Malinao', 'Manalo', 'Mangahas', 'Mangubat', 'Manlapig', 'Manuel',
'Marasigan', 'Marquez', 'Martel', 'Matic', 'Melendres', 'Meneses',
'Miranda', 'Mojica', 'Montero', 'Montoya', 'Morante', 'Moreno', 'Moya',
'Naval', 'Nieva', 'Nieto', 'Nieves', 'Nolasco', 'Obando', 'Ocampo',
'Oliva', 'Olivares', 'Ong', 'Ordonez', 'Ortega', 'Ortiz', 'Osorio',
'Padilla', 'Paguio', 'Palacio', 'Palma', 'Pangan', 'Panganiban',
'Panlilio', 'Pantoja', 'Paredes', 'Parilla', 'Parungao', 'Pasco', 'Pastor',
'Patricio', 'Pineda', 'Pizarro', 'Po', 'Policarpio', 'Ponce', 'Quijano',
'Quimpo', 'Quinto', 'Quirino', 'Rafael', 'Ramoso', 'Razon', 'Redillas',
'Relucio', 'Remulla', 'Riego', 'Rigor', 'Rivadeneira', 'Rizal', 'Robles',
'Rocha', 'Rodriguez', 'Rojo', 'Romualdez', 'Rosa', 'Rosales', 'Rosario',
'Rueda', 'Ruiz', 'Sablan', 'Salas', 'Salcedo', 'Salinas', 'Samson',
'San Juan', 'San Miguel', 'Sandoval', 'Santillan', 'Santoson', 'Sarmiento',
'Segovia', 'Sereno', 'Sia', 'Silang', 'Silva', 'Sison', 'Soledad',
'Soliman', 'Soriano', 'Subido', 'Suarez', 'Sumangil', 'Sy', 'Tablante',
'Tabora', 'Tacorda', 'Tagle', 'Tamayo', 'Tan', 'Tangonan', 'Tantoco',
'Tapales', 'Taruc', 'Tejada', 'Tiongson', 'Tolentino', 'Tongco', 'Toribio',
'Trinidad', 'Tronqued', 'Tuazon', 'Ubaldo', 'Ugalde', 'Umali', 'Untalan',
'Uy', 'Valencia', 'Valenton', 'Valera', 'Valle', 'Vargas', 'Velasco',
'Velasquez', 'Vergara', 'Verzosa', 'Villafuerte', 'Villalobos', 'Villamor',
'Villanueva', 'Villareal', 'Vizcarra', 'Yamamoto', 'Yap', 'Yatco', 'Yumul',
'Zabala', 'Zamora', 'Zarate', 'Zavalla', 'Zialcita', 'dela Cruz',
'Perez', 'Gomez', 'Rodriguez', 'Sanchez', 'Ramirez', 'Francisco', 'Pascual', 'Hernandez', 'Aguilar',
'Diaz', 'Lim', 'Chua', 'Uy', 'Co', 'Lee', 'Chan', 'Yap', 'Manalo', 'Panganiban', 'Marasigan',
'Agbayani', 'Macapagal',
'Abad', 'Abadiano', 'Abalos', 'Abanilla', 'Abanto', 'Abarca',
'Abaya', 'Abella', 'Abesamis', 'Abiera', 'Abinoja', 'Abisamis',
'Ablan', 'Ablaza', 'Abordo', 'Abrigo', 'Abril', 'Abucay', 'Abunda',
'Acabo', 'Acal', 'Acedera', 'Acevedo', 'Acosta', 'Adajar',
'Adan', 'Adarlo', 'Adaza', 'Adlawan', 'Adolfo', 'Adriano',
'Agbayani', 'Agcaoili', 'Agda', 'Agdeppa', 'Agero', 'Agliam',
'Aglibot', 'Agmata', 'Agnes', 'Agoncillo', 'Agpaoa', 'Agregado',
'Aguado', 'Aguila', 'Aguilar', 'Aguilera', 'Aguinaldo', 'Aguirre',
'Alarcon', 'Alba', 'Albano', 'Alcaraz', 'Alcazar', 'Alcober',
'Alcoseba', 'Alcuizar', 'Aldaba', 'Alday', 'Alegria', 'Alejandrino',
'Alejo', 'Alfonso', 'Aliño', 'Alinsangan', 'Allarde', 'Almeda',
'Almirante', 'Almonte', 'Almuete', 'Almario', 'Alonte', 'Alonzo',
'Alvarado', 'Alvarez', 'Amador', 'Amante', 'Amarillo', 'Amatong',
'Ambao', 'Ambrosio', 'Amistoso', 'Amores', 'Amparo', 'Ampil',
'Amurao', 'Anacleto', 'Ancheta', 'Andal', 'Andrada', 'Andres',
'Andrin', 'Ang', 'Angara', 'Angeles', 'Angping', 'Aniban',
'Aniceto', 'Anonas', 'Antiporda', 'Antonio', 'Antoque', 'Anunciacion',
'Apolonio', 'Apostol', 'Aquino', 'Araneta', 'Arce', 'Arcega',
'Arceo', 'Arciaga', 'Arcilla', 'Arellano', 'Arevalo', 'Arguelles',
'Aristores', 'Arnaiz', 'Arnaldo', 'Arriola', 'Arroyo', 'Arsenio',
'Asis', 'Asistio', 'Asuncion', 'Atienza', 'Aurelio', 'Austria',
'Avila', 'Ayala', 'Ayson', 'Azarcon', 'Azores',
'Bacani', 'Baclig', 'Bacungan', 'Badajos', 'Badayos', 'Badillo',
'Bagalay', 'Bagatsing', 'Bagay', 'Bagongon', 'Baguio', 'Bahena',
'Bailon', 'Balanay', 'Balane', 'Balatbat', 'Baldonado', 'Baldo',
'Baldoza', 'Baldovino', 'Balingit', 'Ballesteros', 'Balmeo', 'Balmes',
'Balmonte', 'Baluyot', 'Banaag', 'Banal', 'Banaria', 'Bangayan',
'Bangco', 'Bangoy', 'Banlaoi', 'Banzon', 'Baranda', 'Barba',
'Barcena', 'Barcelona', 'Barela', 'Bargas', 'Bariso', 'Barlaan',
'Barrientos', 'Barroga', 'Barsaga', 'Bartolome', 'Basco', 'Basilio',
'Batungbakal', 'Bautista', 'Bayani', 'Baylon', 'Bayona', 'Bayot',
'Beltran', 'Belmonte', 'Benitez', 'Bernabe', 'Bernardo', 'Bersamin',
'Blanco', 'Bonifacio', 'Borja', 'Borlongan', 'Borromeo',
'Braganza', 'Bravo', 'Brillantes', 'Briones', 'Buenaventura', 'Buendia',
'Bueno', 'Bugay', 'Bulaon', 'Bulanadi', 'Bulatao', 'Bunag',
'Burgos', 'Bustamante', 'Caballero', 'Cabanilla', 'Cabrera',
'Cabatingan', 'Cadiz', 'Calderon', 'Camacho', 'Camara', 'Campos',
'Candelaria', 'Canlas', 'Canoy', 'Carandang', 'Caraig', 'Carating',
'Cariño', 'Carreon', 'Carrillo', 'Carungay', 'Casal', 'Casanova',
'Casimiro', 'Castaneda', 'Castillo', 'Castro', 'Catapang',
'Cayabyab', 'Cayetano', 'Celestino', 'Celis', 'Centeno', 'Cervantes',
'Chavez', 'Chua', 'Cipriano', 'Clarin', 'Claudio', 'Clemente',
'Co', 'Concepcion', 'Cordero', 'Cordova', 'Cornejo', 'Coronel',
'Corpuz', 'Corral', 'Cortez', 'Crisologo', 'Crisostomo', 'Cruz',
'Cuenca', 'Cunanan', 'Custodio', 'Dacanay', 'Daguio', 'Dalisay',
'Damasco', 'Dancel', 'Dantes', 'David', 'Davila', 'Decena',
'Delacruz', 'Delgado', 'Delima', 'Delos Reyes', 'Del Rosario',
'Desiderio', 'DeVera', 'Diaz', 'Dichoso', 'Dimalanta', 'Dimaculangan',
'Dimagiba', 'Dinglasan', 'Dionisio', 'Dizon', 'Docena', 'Dolor',
'Domingo', 'Dominguez', 'Donato', 'Duenas', 'Dulay', 'Dumo',
'Durano', 'Ebarle', 'Echevarria', 'Edralin', 'Elizalde',
'Encarnacion', 'Enriquez', 'Enrile', 'Escalante', 'Escobar',
'Escueta', 'Escudero', 'Espinosa', 'Espiritu', 'Estacion', 'Esteban',
'Estrella', 'Estrada', 'Evangelista', 'Fabian', 'Fajardo', 'Falcon',
'Fajardo', 'Feliciano', 'Felipe', 'Fernandez', 'Fernan', 'Ferraren',
'Ferrolino', 'Ferrer', 'Figueroa', 'Florencio', 'Flores', 'Fontanilla',
'Francisco', 'Fuentes', 'Galang', 'Galvez', 'Gamboa', 'Garay',
'Garcia', 'Garing', 'Garrido', 'Gaspar', 'Gatchalian', 'Gatdula',
'Gatmaitan', 'Gavino', 'Geronimo', 'Giron', 'Gomez', 'Gonzaga',
'Gonzales', 'Gonzalez', 'Guerrero', 'Guevarra', 'Guinto', 'Gutierrez',
'Guzman', 'Habana', 'Halili', 'Hernandez', 'Herrera', 'Hidalgo',
'Hilario', 'Honasan', 'Hontiveros', 'Ignacio', 'Ilagan', 'Imperial',
'Inocencio', 'Isidro', 'Jacinto', 'Javier', 'Jimenez', 'Joaquin',
'Jocson', 'Kalaw', 'Katigbak', 'Lacson', 'Lagman', 'Lapid',
'Laurel', 'Lazaro', 'Ledesma', 'Legarda', 'Legaspi', 'Leonico',
'Lim', 'Liwanag', 'Locsin', 'Lopez', 'Lorenzana', 'Lorenzo',
'Loyola', 'Lozada', 'Lucero', 'Luna', 'Mabini', 'Macapagal',
'Macaraig', 'Magsaysay', 'Manalo', 'Manalac', 'Manglapus', 'Marasigan',
'Marcos', 'Mariano', 'Marquez', 'Martinez', 'Mateo', 'Matias',
'Medalla', 'Medina', 'Mercado', 'Miranda', 'Molina', 'Montano',
'Montenegro', 'Montero', 'Morales', 'Moreno', 'Nakpil', 'Narciso',
'Navarro', 'Nepomuceno', 'Neri', 'Nicolas', 'Nieto', 'Nolasco',
'Ocampo', 'Ordonez', 'Ortigas', 'Osmeña', 'Padilla', 'Palma',
'Panganiban', 'Pangilinan', 'Panlilio', 'Pantaleon', 'Paraiso', 'Pascual',
'Pastor', 'Paterno', 'Pelayo', 'Peña', 'Peralta', 'Perez',
'Pimentel', 'Pineda', 'Ponce', 'Puno', 'Punsalan', 'Quezon',
'Quirino', 'Ramirez', 'Ramos', 'Razon', 'Recto', 'Regalado',
'Revilla', 'Ricarte', 'Rivera', 'Robles', 'Rodriguez', 'Rojo',
'Roldan', 'Romero', 'Romualdez', 'Romulo', 'Roque', 'Rosales',
'Rosario', 'Roxas', 'Rubio', 'Ruiz', 'Salas', 'Salazar',
'Salcedo', 'Salonga', 'Salvador', 'Samonte', 'San Agustin', 'San Jose',
'San Juan', 'San Pedro', 'Sanchez', 'Santiago', 'Santillan', 'Sarmiento',
'Sebastian', 'Segovia', 'Silang', 'Singson', 'Sison', 'Soliman',
'Soriano', 'Sotto', 'Suarez', 'Sumulong', 'Sy', 'Tagle', 'Tamayo',
'Tan', 'Tantoco', 'Tapales', 'Tayag', 'Teodoro', 'Teves',
'Tolentino', 'Tordesillas', 'Torres', 'Trinidad', 'Tuason', 'Tugade',
'Ty', 'Umali', 'Uy', 'Valdez', 'Valencia', 'Valenzuela', 'Valera',
'Vargas', 'Velasco', 'Velasquez', 'Ventura', 'Vergara', 'Verzosa',
'Villafuerte', 'Villamor', 'Villanueva', 'Villareal', 'Villegas',
'Vinluan', 'Yap', 'Yumul', 'Zabala', 'Zaldivar', 'Zamora',
'Zapanta', 'Zarate', 'Zerrudo', 'Zialcita', 'Zobel', 'Zulueta',
]

def get_bd_name():
    first = random.choice(first_names_male + first_names_female)
    last = random.choice(surnames)
    return first, last

rpw_first_names = [
'Luna', 'Aurora', 'Mystic', 'Crystal', 'Sapphire', 'Scarlet', 'Violet',
'Rose', 'Athena', 'Venus', 'Nova', 'Stella', 'Serena', 'Raven', 'Jade',
'Ruby', 'Pearl', 'Ivy', 'Willow', 'Hazel', 'Skye', 'Aria', 'Melody',
'Harmony', 'Grace', 'Faith', 'Hope', 'Trinity', 'Destiny', 'Serenity',
'Angel', 'Star', 'Astra', 'Lyra', 'Celeste', 'Elara', 'Elysia', 'Raine',
'Sylvie', 'Nahara', 'Isolde', 'Ophelia', 'Althea', 'Calista', 'Delara',
'Eira', 'Freya', 'Gaia', 'Helena', 'Ilara', 'Junia', 'Kaia', 'Liora',
'Maeve', 'Nara', 'Odessa', 'Phoebe', 'Quinn', 'Rhea', 'Selene', 'Thalia',
'Una', 'Vanya', 'Wynter', 'Xanthe', 'Yara', 'Zara', 'Amara', 'Aurelia',
'Brina', 'Celine', 'Dahlia', 'Eden', 'Fiona', 'Gwen', 'Helia', 'Isla',
'Jessa', 'Kara', 'Lilia', 'Mara', 'Nerine', 'Oona', 'Perse', 'Runa',
'Sana', 'Tara', 'Vera', 'Willa', 'Xena', 'Yvaine', 'Zinnia', 'Aislinn',
'Arielle', 'Belladonna', 'Briar', 'Cassia', 'Daphne', 'Eleni', 'Flora',
'Gemma', 'Hera', 'Ione', 'Jadea', 'Kaira', 'Lilith', 'Maven', 'Nerida',
'Orla', 'Petra', 'Quilla', 'Risa', 'Saphira', 'Tessa', 'Vixie', 'Wren',
'Yuna', 'Zelie', 'Aiyana', 'Ameera', 'Blaire', 'Camina', 'Daria', 'Eirene',
'Faye', 'Greta', 'Honora', 'Indira', 'Jolie', 'Kahlia', 'Lunara', 'Maris',
'Nixie', 'Oriana', 'Phaedra', 'Reina', 'Soleil', 'Tahlia', 'Viera',
'Whisper', 'Xylia', 'Yasmin', 'Zephyra', 'Adira', 'Ariya', 'Brienne',
'Coraline', 'Dove', 'Emberly', 'Fable', 'Giselle', 'Harlow', 'Ivyra',
'Jorah', 'Keira', 'Lyrra', 'Mirelle', 'Nimue', 'Ophira', 'Paloma', 'Rivka',
'Sarai', 'Tirzah', 'Velia', 'Wynna', 'Xaria', 'Yllia', 'Zalina', 'Amoura',
'Aven', 'Brisa', 'Cassidy', 'Diantha', 'Elva', 'Farrah', 'Giada', 'Hollis',
'Inara', 'Jadeen', 'Kiera', 'Leira', 'Maelle', 'Naida', 'Orra', 'Pyria',
'Riona', 'Saphine', 'Tova', 'Vanyael', 'Winry', 'Xavia', 'Ysella', 'Zyria',
'Alera', 'Arwen', 'Brielle', 'Cyrene', 'Deira', 'Evania', 'Fianna',
'Gwenna', 'Halyn', 'Irina', 'Jovina', 'Kaelia', 'Luneth', 'Mariel',
'Nayla', 'Orelle', 'Phaena', 'Ruelle', 'Sylph', 'Thessaly', 'Valea',
'Wynnair', 'Xenara', 'Ysolde', 'Zamira', 'Alira', 'Amaris', 'Brynna',
'Ceres', 'Delyra', 'Eislyn', 'Fiora', 'Gwyne', 'Haelia', 'Ismena', 'Jalyn',
'Katria', 'Liorael', 'Maelis', 'Nessara', 'Ovelyn', 'Prisma', 'Ravine',
'Seraphine', 'Tahlira', 'Vierael', 'Wyndra', 'Xylara', 'Yvanna', 'Zerina',
'Anora', 'Aveline', 'Brienne', 'Cynra', 'Danea', 'Eirlys', 'Fael', 'Giana',
'Hessia', 'Ilona', 'Janessa', 'Kyria', 'Lirael', 'Madria', 'Norelle',
'Ophirae', 'Paela', 'Quina', 'Rilith', 'Sienna', 'Tiriel', 'Velisse',
'Wrena', 'Xamira', 'Ysenne', 'Zynra', 'Aelina', 'Alessa', 'Belwyn',
'Carmine', 'Daelia', 'Elyndra', 'Fiorael', 'Gwyneth', 'Helis', 'Isola',
'Jynra', 'Kailen', 'Lunisse', 'Mynra', 'Nyelle', 'Orissa', 'Phira',
'Rylis', 'Saphyre', 'Thyra', 'Valyn', 'Wynelle', 'Xira', 'Ylith', 'Zayra',
'Avenia', 'Ariael', 'Blythe', 'Corra', 'Delyth', 'Elaina', 'Fara', 'Gisra',
'Hellen', 'Ionea', 'Jalisa', 'Kayle', 'Lysandra', 'Mirael', 'Nysa',
'Ophirael', 'Phaelia', 'Renelle', 'Saphra', 'Tirra', 'Viona', 'Wynlie',
'Xynna', 'Ylia', 'Zinnara', 'Azura', 'Bliss', 'Cassiel', 'Dionne',
'Elaris', 'Fawn', 'Gloria', 'Haelyn', 'Inessa', 'Jael', 'Koryn', 'Lissara',
'Marenne', 'Hiraya', 'Celestine', 'Aurora', 'Astrid', 'Brielle', 'Calista', 'Davina', 'Elara', 'Freya', 'Genevieve',
'Haven', 'Iris', 'Juliet', 'Kaia', 'Lyra', 'Mira', 'Nova', 'Ophelia', 'Persephone', 'Quinn',
'Rosalie', 'Seraphina', 'Thea', 'Valencia', 'Willow', 'Xandra', 'Yara', 'Zara', 'Athena', 'Bianca', 'Hiraya', 'Seraphina', 'Anastasia', 'Celestine', 'Evangeline', 'Isadora',
'Genevieve', 'Arabella', 'Josephine', 'Valentina', 'Alessandra', 'Cassandra',
'Gabriella', 'Penelope', 'Rosalind', 'Vivienne', 'Arabesque', 'Beatrice',
'Clementine', 'Delphine', 'Esmeralda', 'Francesca', 'Gwendolyn',
'Isolde', 'Juliette', 'Katarina', 'Lavender', 'Magdalena', 'Nicolette',
'Ophelia', 'Persephone', 'Queenie', 'Rosabelle', 'Sapphire', 'Theodora',
'Valencia', 'Wilhelmina', 'Xanthia', 'Zenaida', 'Aureliana',
'Bernadette', 'Celestia', 'Desdemona', 'Fallon', 'Flannery', 'Kaie',
'Kaitlyn', 'Kassidy', 'Kathleen', 'Keena', 'Keira',
'Kendall', 'Kenna', 'Kera', 'Kiara',
'Kirra', 'Kylee', 'Lachlan', 'Lorna', 'Maeve', 'Malise',
'Morgance', 'Morgandy', 'Nonnita', 'Nuala', 'Raelin', 'Rhonda',
'Saoirse', 'Saraid', 'Seanna', 'Shela', 'Shylah', 'Tara',
'Teranika', 'Tieve', 'Treasa', 'Treva', 'Addison', 'Alivia',
'Allaya', 'Amarie', 'Amaris', 'Annabeth', 'Annalynn', 'Araminta',
'Ardys', 'Ashland', 'Avery', 'Bernadette', 'Billie',
'Birdee', 'Bliss', 'Brice', 'Brittany', 'Bryony', 'Cameo',
'Carol', 'Chalee', 'Christy', 'Corky', 'Courage',
'Daelen', 'Dana', 'Darnell', 'Dawn', 'Delsie', 'Denita',
'Devon', 'Devona', 'Diamond', 'Divinity', 'Dusty',
'Ellen', 'Eppie', 'Evelyn', 'Everilda', 'Falynn',
'Fanny', 'Faren', 'Freedom', 'Gala', 'Galen', 'Gardenia',
'Germain', 'Gig', 'Gilda', 'Giselle', 'Githa', 'Haiden',
'Halston', 'Heather', 'Henna', 'Honey', 'Idalis',
'Ilsa', 'Jersey', 'Jette', 'Jill', 'Joanna',
'Kachelle', 'Kade', 'Kady', 'Kaela', 'Kalyn', 'Kandice',
'Karrie', 'Karyn', 'Katiuscia', 'Kempley', 'Kenda', 'Kennice',
'Kenyon', 'Kiandra', 'Kimber', 'Kimn', 'Kinsey',
'Kipp', 'Kismet', 'Kortney', 'Kourtney',
'Kristal', 'Kylar', 'Ladawn', 'Ladye', 'Lainey',
'Lake', 'Lalisa', 'Landen', 'Landon', 'Landry', 'Laney',
'Langley', 'Lanna', 'Laquetta', 'Lari', 'Lark', 'Laurel',
'Lavender', 'Leane', 'LeAnn', 'Leanna', 'Leanne', 'Leanore',
'Lee', 'Leeann', 'Leighanna', 'Lexie', 'Lexis', 'Liberty',
'Liliana', 'Lillian', 'Lindley', 'Linne', 'Liora', 'Lisabet',
'Liz', 'Lizette', 'Lona', 'London', 'Loni', 'Lorena',
'Loretta', 'Lovette', 'Lynde', 'Lyndon', 'Lyndsay', 'Lynette',
'Lynley', 'Lynna', 'Lynton', 'Mada', 'Maddox', 'Madison',
'Mae', 'Maggie', 'Mahogany', 'Maia', 'Maitane', 'Maitland',
'Malachite', 'Mamie', 'Manhattan', 'Maridel', 'Marla', 'Marley',
'Marliss', 'Maud', 'May', 'Merleen', 'Mildred',
'Milissa', 'Millicent', 'Mily', 'Mykala', 'Nan',
'Nautica', 'Nelda', 'Niki', 'Nikole', 'Nimue', 'Nineve',
'Norina', 'Ofa', 'Palmer', 'Pansy', 'Paris', 'Patience',
'Patricia', 'Peony', 'Petunia', 'Pixie', 'Pleasance', 'Polly',
'Primrose', 'Princell', 'Providence', 'Purity', 'Quanah', 'Queena',
'Quella', 'Quinci', 'Rae', 'Rainbow', 'Rainelle', 'Raleigh',
'Ralphina', 'Randi', 'Raven', 'Rayelle', 'Rea', 'Remington',
'Richelle', 'Ripley', 'Roberta', 'Robin', 'Rosemary', 'Rowan',
'Rumer', 'Ryesen', 'Sable', 'Sadie', 'Saffron', 'Saga',
'Saige', 'Salal', 'Salia', 'Sandora', 'Sebille', 'Sebrina',
'Selby', 'Serenity', 'Shae', 'Shandy', 'Shanice', 'Sharman',
'Shelbi', 'Sheldon', 'Shelley', 'Sheridan', 'Sherill', 'Sheryl',
'Sheyla', 'Shirley', 'Shirlyn', 'Silver', 'Skyla', 'Skylar',
'Sorilbran', 'Sparrow', 'Spring', 'Starleen', 'Stockard', 'Storm',
'Sudie', 'Summer', 'Sunniva', 'Suzana', 'Symphony', 'Tacey',
'Tahnee', 'Taite', 'Talon', 'Tambre', 'Tamia', 'Taniya',
'Tanner', 'Tanzi', 'Taria', 'Tate', 'Tatum', 'Tawnie',
'Taya', 'Tayla', 'Taylor', 'Tayna', 'Teddi', 'Tena',
'Tera', 'Teri', 'Teryl', 'Thistle', 'Timotha', 'Tinble',
'Tosha', 'Totie', 'Traci', 'Tru', 'Trudie', 'Trudy',
'Tryamon', 'Tuesday', 'Twila', 'Twyla', 'Tyne', 'Udele',
'Unity', 'Vail', 'Vala', 'Velvet', 'Venetta', 'Walker',
'Wallis', 'Waneta', 'Waverly', 'Wendy', 'Weslee', 'Whitley',
'Whitney', 'Whoopi', 'Wilda', 'Wilfreda', 'Willow', 'Wilona',
'Winifred', 'Winsome', 'Winter', 'Wisdom', 'Wrenn', 'Yale',
'Yardley', 'Yeardley', 'Yedda', 'Young', 'Ysolde', 'Zadie',
'Zanda', 'Zavannah', 'Zavia', 'Zeolia', 'Zinnia', 'Blaine',
'Blair', 'Eilis', 'Kalene', 'Keaira', 'Keelty', 'Keely',
'Keen', 'Keitha', 'Kellan', 'Kennis', 'Kerry', 'Kevina',
'Killian', 'Kyna', 'Lakyle', 'Lee', 'Mab', 'Maeryn',
'Maille', 'Mairi', 'Maisie', 'Meara', 'Meckenzie', 'Myrna',
'Nara', 'Neala', 'Nelia', 'Oona', 'Quinn', 'Rhoswen',
'Riane', 'Riley', 'Rogan', 'Rona', 'Ryan', 'Sadb',
'Shanley', 'Shelagh', 'Sine', 'Siobhan', 'Sorcha', 'Ultreia',
'Vevila', 'Acantha', 'Adara', 'Adelpha', 'Adrienne', 'Aegle',
'Afrodite', 'Agape', 'Agata', 'Aglaia', 'Agnes', 'Aileen',
'Alcina', 'Aldora', 'Alethea', 'Alexandra', 'Alice', 'Alida',
'Alisha', 'Alixia', 'Althea', 'Aludra', 'Amara', 'Ambrosia',
'Amethyst', 'Aminta', 'Amphitrite', 'Anastasia', 'Andrea', 'Andromache',
'Andromeda', 'Angela', 'Anstice', 'Antonia', 'Anysia', 'Aphrodite',
'Arali', 'Aretha', 'Ariadne', 'Ariana', 'Arissa',
'Artemia', 'Artemis', 'Astrid', 'Athena', 'Atropos', 'Aurora',
'Avel', 'Basilissa', 'Bernice', 'Calandra',
'Calantha', 'Calista', 'Calliope', 'Candace', 'Candra', 'Carina',
'Carisa', 'Cassandra', 'Cassiopeia', 'Catherine', 'Celandia', 'Cerelia', 'Charisma', 'Christina', 'Clio', 'Cloris',
'Clotho', 'Colette', 'Cora', 'Cressida', 'Cybill', 'Cyd',
'Cynthia', 'Damaris', 'Damia', 'Daphne', 'Daria', 'Daryn',
'Dasha', 'Dea', 'Delbin', 'Della', 'Delphine', 'Delta',
'Demetria', 'Desdemona', 'Desma', 'Despina', 'Dionne', 'Diotama',
'Dora', 'Dorcas', 'Doria', 'Dorian', 'Doris', 'Dorothy',
'Dorrit', 'Drew', 'Drucilla', 'Dysis', 'Ebony', 'Effie',
'Eileen', 'Elani', 'Eleanor', 'Electra', 'Elke', 'Elma',
'Elodie', 'Eos', 'Eppie', 'Eris', 'Ethereal', 'Eudora',
'Eugenia', 'Eulalia', 'Eunice', 'Euphemia', 'Euphrosyne', 'Euterpe',
'Evadne', 'Evangeline', 'Filmena', 'Gaea', 'Galina', 'Gelasia',
'Gemini', 'Georgia', 'Greer', 'Greta', 'Harmony', 'Hebe',
'Hecate', 'Hecuba', 'Helen', 'Hera', 'Hermia', 'Hermione',
'Hero', 'Hestia', 'Hilary', 'Hippolyta', 'Hyacinth', 'Hydra',
'Ianthe', 'Ilena', 'Iolite', 'Iona', 'Irene', 'Iris',
'Isidore', 'Jacey', 'Jacinta', 'Jolanta', 'Kacia', 'Kaethe',
'Kaia', 'Kaija', 'Kairi', 'Kairos', 'Kali', 'Kalidas',
'Kalika', 'Kalista', 'Kalli', 'Kalliope', 'Kallista', 'Kalonice',
'Kalyca', 'Kanchana', 'Kandace', 'Kara', 'Karana', 'Karen',
'Karin', 'Karis', 'Karissa', 'Karlyn', 'Kasandra', 'Kassandra',
'Katarina', 'Kate', 'Katherine', 'Katina', 'Khina', 'Kineta',
'Kirsten', 'Kolina', 'Kora', 'Koren', 'Kori', 'Korina',
'Kosma', 'Kristen', 'Kristi', 'Kristina', 'Kristine', 'Kristy',
'Kristyn', 'Krysten', 'Krystina', 'Kynthia', 'Kyra', 'Kyrene',
'Kyria', 'Lacy', 'Lali', 'Lareina', 'Laria', 'Larina',
'Larisa', 'Larissa', 'Lasthenia', 'Latona', 'Layna', 'Leandra',
'Leda', 'Ledell', 'Lenore', 'Leonora', 'Leta', 'Letha',
'Lethia', 'Lexi', 'Lexie', 'Lidia', 'Lilika', 'Lina',
'Linore', 'Litsa', 'Livana', 'Livvy', 'Lotus', 'Lyanne',
'Lycorida', 'Lycoris', 'Lydia', 'Lydie', 'Lykaios', 'Lyra',
'Lyric', 'Lyris', 'Lysandra', 'Macaria', 'Madalena', 'Madelia',
'Madeline', 'Madge', 'Maeve', 'Magan', 'Magdalen', 'Maia',
'Mala', 'Malissa', 'Mara', 'Margaret', 'Marigold', 'Marilee',
'Marjorie', 'Marlene', 'Marmara', 'Maya', 'Medea', 'Medora',
'Megan', 'Megara', 'Melanctha', 'Melanie', 'Melba', 'Melenna',
'Melia', 'Melinda', 'Melissa', 'Melitta', 'Melody', 'Melpomene',
'Minta', 'Mnemosyne', 'Mona', 'Muse', 'Myda', 'Myrtle',
'Naia', 'Naida', 'Naiyah', 'Narcissa', 'Narella', 'Natasha',
'Nell', 'Nellie', 'Nellis', 'Nelly', 'Neola', 'Neoma',
'Nerin', 'Nerina', 'Neysa', 'Nichole', 'Nicia', 'Nicki',
'Nicole', 'Nike', 'Nikita', 'Niobe', 'Nitsa', 'Noire',
'Nora', 'Nyla', 'Nysa', 'Nyssa', 'Nyx', 'Obelia',
'Oceana', 'Odea', 'Odessa', 'Ofelia', 'Olympia', 'Omega',
'Onyx', 'Ophelia', 'Ophira', 'Orea', 'Oriana', 'Padgett',
'Pallas', 'Pamela', 'Pandora', 'Panphila', 'Parthenia', 'Pelagia',
'Penelope', 'Phedra', 'Philadelphia', 'Philippa', 'Philomena', 'Phoebe',
'Phyllis', 'Pirene', 'Prisma', 'Psyche', 'Ptolema', 'Pyhrrha',
'Pyrena', 'Pythia', 'Raissa', 'Rasia', 'Rene', 'Rhea',
'Rhoda', 'Rhodanthe', 'Rita', 'Rizpah', 'Saba', 'Sandra',
'Sandrine', 'Sapphira', 'Sappho', 'Seema', 'Selena', 'Selina',
'Sema', 'Sherise', 'Sibley', 'Sirena', 'Sofi', 'Sondra',
'Sophie', 'Sophronia', 'Stacia', 'Stefania',
'Stephaney', 'Stesha', 'Sybella', 'Sybil', 'Syna', 'Tabitha',
'Talia', 'Talieya', 'Taliyah', 'Tallya', 'Tamesis', 'Tanith',
'Tansy', 'Taryn', 'Tasha', 'Tasia', 'Tedra', 'Teigra',
'Tekla', 'Telma', 'Terentia', 'Terpsichore', 'Terri', 'Tess',
'Thaddea', 'Thaisa', 'Thalassa', 'Thalia', 'Than', 'Thea',
'Thelma', 'Themis', 'Theodora', 'Theodosia', 'Theola', 'Theone',
'Theophilia', 'Thera', 'Theresa', 'Thisbe', 'Thomasa', 'Thracia',
'Thyra', 'Tiana', 'Tienette', 'Timandra', 'Timothea', 'Titania',
'Titian', 'Tomai', 'Tona', 'Tresa', 'Tressa', 'Triana',
'Trifine', 'Trina', 'Tryna', 'Urania', 'Uriana', 'Vanessa',
'Vasiliki', 'Velma', 'Venus', 'Voleta', 'Xandria', 'Xandy',
'Xantha', 'Xenia', 'Xenobia', 'Xianthippe', 'Xylia', 'Xylona',
'Yolanda', 'Yolie', 'Zagros', 'Zale', 'Zanaide', 'Zandra',
'Zanita', 'Zanthe', 'Zebina', 'Zelia', 'Zena', 'Zenaide',
'Zenia', 'Zenobia', 'Zenon', 'Zera', 'Zeta', 'Zeuti',
'Zeva', 'Zinaida', 'Zoe', 'Zosima', 'Ai', 'Aiko',
'Akako', 'Akanah', 'Aki', 'Akina', 'Akiyama', 'Amarante',
'Amaya', 'Aneko', 'Anzan', 'Anzu', 'Aoi', 'Asa',
'Asami', 'Ayame', 'Bankei', 'Chika', 'Chihiro',
'Chiyo', 'Cho', 'Chorei', 'Dai', 'Eido', 'Ema',
'Etsu', 'Fuyo', 'Hakue', 'Hama', 'Hanako',
'Haya', 'Hisa', 'Himari', 'Hoshi', 'Ima', 'Ishi',
'Iva', 'Jimin', 'Jin', 'Jun', 'Junko',
'Kaede', 'Kagami', 'Kaida', 'Kaiya', 'Kameko',
'Kamin', 'Kanako', 'Kane', 'Kaori', 'Kaoru', 'Kata',
'Kaya', 'Kei', 'Keiko', 'Kiaria', 'Kichi', 'Kiku',
'Kimi', 'Kin', 'Kioko', 'Kira', 'Kita', 'Kiwa',
'Kiyoshi', 'Kohana', 'Koto', 'Kozue',
'Kuma', 'Kumi', 'Kumiko', 'Kuniko', 'Kura', 'Kyoko',
'Leiko', 'Machi', 'Machiko', 'Maeko', 'Maemi', 'Mai',
'Maiko', 'Makiko', 'Mamiko', 'Mariko', 'Masago', 'Masako',
'Matsuko', 'Mayako', 'Mayuko', 'Michi', 'Michiko', 'Midori',
'Mieko', 'Mihoko', 'Mika', 'Miki', 'Minako', 'Minato',
'Mine', 'Misako', 'Misato', 'Mitsuko', 'Miwa', 'Miya',
'Miyoko', 'Miyuki', 'Momoko', 'Mutsuko', 'Myoki', 'Nahoko',
'Nami', 'Nanako', 'Nanami', 'Naoko', 'Naomi', 'Nariko',
'Natsuko', 'Nayoko', 'Nishi', 'Nori', 'Noriko', 'Nozomi',
'Nyoko', 'Oki', 'Rai', 'Raku', 'Rei', 'Reina',
'Reiko', 'Ren', 'Renora', 'Rieko', 'Rikako', 'Riku',
'Rinako', 'Rin', 'Rini', 'Risako', 'Ritsuko', 'Roshin',
'Rumiko', 'Ruri', 'Ryoko', 'Sachi', 'Sachiko', 'Sada',
'Saeko', 'Saiun', 'Saki', 'Sakiko', 'Sakuko', 'Sakura',
'Sakurako', 'Sanako', 'Sasa', 'Sashi', 'Sato', 'Satoko',
'Sawa', 'Sayo', 'Sayoko', 'Seki', 'Shika', 'Shikah',
'Shina', 'Shinko', 'Shoko', 'Sorano', 'Suki', 'Sumi',
'Tadako', 'Taido', 'Taka', 'Takako', 'Takara', 'Taki',
'Tamaka', 'Tamiko', 'Tanaka', 'Taney', 'Tani', 'Taree',
'Tazu', 'Tennen', 'Tetsu', 'Tokiko', 'Tomi', 'Tomiko',
'Tora', 'Tori', 'Toyo', 'Tsubame', 'Umeko', 'Usagi',
'Wakana', 'Washi', 'Yachi', 'Yaki', 'Yama', 'Yasu',
'Yayoi', 'Yei', 'Yoi', 'Yoko', 'Yori', 'Yoshiko',
'Yuka', 'Yukako', 'Yukiko', 'Yumi', 'Yumiko', 'Yuri',
'Yuriko', 'Yutsuko',
]

rpw_surnames = [
'Shadow', 'Dark', 'Light', 'Star', 'Moon', 'Sun', 'Sky', 'Night', 'Dawn',
'Storm', 'Frost', 'Fire', 'Stanley', 'Nero', 'Clifford', 'Volsckev',
'Draven', 'Smith', 'Greisler', 'Wraith', 'Hale', 'Voss', 'Lockhart',
'Ashford', 'Wynters', 'Grayson', 'Ravenwood', 'Langford', 'Averill',
'Cross', 'Kane', 'Holloway', 'Mercer', 'Devereux', 'Vale', 'Alden',
'Blackwell', 'Marcellis', 'Vossler', 'Crane', 'Laurent', 'Radcliffe',
'Hadrian', 'Vexley', 'Roth', 'Everhart', 'Winslow', 'Fayden', 'Crawford',
'Ashborne', 'Davenport', 'Drayton', 'Sutherland', 'Vayne', 'Rosenthal',
'Arkwright', 'Devere', 'Langley', 'Kingsley', 'Vanora', 'Astor',
'Carrington', 'Trevane', 'Remmington', 'Wolfe', 'Drayke', 'Hawke', 'Briar',
'Sterling', 'Crowhurst', 'Marlowe', 'Hastings', 'Westwood', 'Ravenshire',
'Locke', 'Harrow', 'Draxler', 'Valemont', 'Caine', 'Redgrave', 'Frost',
'Vanthorn', 'Ashcroft', 'Moreau', 'Rothwell', 'Varen', 'Lancaster',
'Ashfield', 'Sinclair', 'Duskwood', 'Vermillion', 'Whitlock', 'Halden',
'Faust', 'Ironwood', 'Drayven', 'Grey', 'Valeheart', 'Caldwell', 'Vosslyn',
'Avenhart', 'Nightray', 'Morraine', 'Leclair', 'Hartgrave', 'Thorne',
'Montclair', 'Ashen', 'Dreyer', 'Stormwell', 'Vossen', 'Gryphon',
'Reinhart', 'Claremont', 'Hartley', 'Nightborne', 'Valentine', 'Dreyson',
'Marchand', 'Blackburn', 'Lucan', 'Callister', 'Hartfield', 'Verden',
'Draymor', 'Feyr', 'Ravencroft', 'Ainsley', 'Crestfall', 'Silvera',
'Gravemont', 'Vinter', 'Beaumont', 'Lockridge', 'Thornefield', 'Ashcroft',
'Crowley', 'Winchester', 'Keller', 'Ravenholm', 'Rosier', 'Everett',
'Valeon', 'Marrow', 'Vossell', 'Ashenwald', 'Wyncrest', 'Durand',
'Montague', 'Dreyke', 'Carmine', 'Verlith', 'Harrington', 'Briarson',
'Corvin', 'Tessler', 'Delane', 'Rayven', 'Fletcher', 'Crosswell',
'Sterren', 'Valeric', 'Blackthorn', 'Davenport', 'Vanix', 'Dravien',
'Vexen', 'Rhyker', 'Krynn', 'Greymont', 'Elridge', 'Locksen', 'Harrowell',
'Valeis', 'Avenor', 'Gravelle', 'Dravenhart', 'Noxford', 'Rothen',
'Vallier', 'Devereaux', 'Stormvale', 'Kain', 'Drevis', 'Marchen',
'Langdon', 'Frostell', 'Haldenne', 'Ravenshade', 'Vairn', 'Wyncliff',
'Greystone', 'Vossmer', 'Ashborne', 'Drexel', 'Rykov', 'Drayven',
'Malvern', 'Greyhart', 'Holloway', 'Wraithson', 'Crowden', 'Valleris',
'Stark', 'Wynther', 'Creswell', 'Torrence', 'Arden', 'Fayre', 'Crawell',
'Thayen', 'Morrick', 'Vanier', 'Drevik', 'Hawthorne', 'Evers', 'Aldric',
'Larkson', 'Valemir', 'Dravelle', 'Rothenwald', 'Greyvale', 'Veyron',
'Craven', 'Frostwyn', 'Vares', 'Ashveil', 'Locken', 'Vandrell', 'Silvern',
'Dawncrest', 'Graves', 'Hartwell', 'Falconer', 'Varnell', 'Ashwynn',
'Dravenor', 'Vollaire', 'Kingswell', 'Vashier', 'Larkwell', 'Auren',
'Ravenson', 'Greyborne', 'Voltaire', 'Halewyn', 'Verrin', 'Blackmore',
'Crimson', 'Wrenford', 'Ravelle', 'Valenor', 'Frostfield', 'Vosswick',
'Hollowcrest', 'Veyson', 'Atheron', 'Veyra', 'Raines', 'Grimmond',
'Ashlynn', 'Draywell', 'Vander', 'Vortan', 'Nightwell', 'Vallence', 'Faye',
'Roswell', 'Stormen', 'Havelock', 'Greys', 'Whitmore', 'Thayne', 'Drevan',
'Halric', 'Ashmere', 'Westhall', 'Wray', 'Norring', 'Dane', 'Valeir',
'Kraiven', 'Vosslin', 'Rynhart', 'Eldren', 'Trevane', 'Greisler',
'Hawthorne', 'Morrin', 'Draylen', 'Aurel', 'Briarson', 'Carter', 'Rexford',
'Lynhart', 'Ashland', 'Frostwick', 'Vanloren', 'Crowe', 'Vynne',
'Rothmere', 'Duskhelm', 'Harron', 'Valecrest', 'Merrin', 'Hawken',
'Dreylor', 'Blackwell', 'Farron', 'Caldren', 'Vanora', 'Hollowen',
'Varelle', 'Draymore', 'Westcliff', 'Alder', 'Gryff', 'Ashlock', 'Volsen',
'Drehl', 'Vayden', 'Ravenholt', 'Vossane', 'Krell', 'Marwen', 'Drace',
'Varenne', 'Lockmere', 'Greysten', 'Hawking', 'Ryswell', 'Drayden',
'Cresden', 'Hallow', 'Ashven', 'Valter', 'Greyson', 'Morrinell', 'Wraith',
'Veyden', 'Falken', 'Ashwell', 'Nero', 'Scavendich', 'Volschev', 'Vermont', 'Suez', 'Ashford', 'Blackwood', 'Crane', 'Draven', 'Everhart',
'Frost', 'Grimshaw', 'Hawthorne', 'Ironwood', 'Kingsley', 'Lancaster', 'Mercer', 'Nightshade', 'Oakley', 'Pembroke',
'Radcliffe', 'Shadowfax', 'Thornfield', 'Underwood', 'Vance', 'Whitmore', 'Sterling', 'Ravencroft', 'Ashbury', 'Blackwell',
]

def get_rpw_name():
    return random.choice(rpw_first_names), random.choice(rpw_surnames)

def get_pass():
    name_part = ''.join(random.choices(string.ascii_letters, k=random.randint(5, 7)))
    name_part = name_part.capitalize() if random.choice([True, False]) else name_part.lower()
    symbol_part = ''.join(random.choices('!@#$%^&*()_+=', k=random.randint(2, 3)))
    digit_part = ''.join(random.choices(string.digits, k=random.randint(2, 4)))
    end_part = ''.join(random.choices(string.ascii_letters, k=random.randint(2, 4)))
    optional_upper = ''.join(random.choices(string.ascii_uppercase, k=random.randint(1, 2)))
    parts = [name_part, symbol_part, digit_part, end_part, optional_upper]
    random.shuffle(parts)
    return ''.join(parts)

def extractor(data):
    soup = BeautifulSoup(data, "html.parser")
    data = {}
    for inputs in soup.find_all("input"):
        name = inputs.get("name")
        value = inputs.get("value")
        if name:
            data[name] = value
    return data

def banner():
    clear_screen()
    print(f"""{G}
 █████╗ ██╗   ██╗████████╗ ██████╗       {R}███████╗██████╗ 
██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗      {R}██╔════╝██╔══██╗
███████║██║   ██║   ██║   ██║   ██║      {R}█████╗  ██████╔╝
██╔══██║██║   ██║   ██║   ██║   ██║      {R}██╔══╝  ██╔══██╗
██║  ██║╚██████╔╝   ██║   ╚██████╔╝      {R}██║     ██████╔╝
╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝       {R}╚═╝     ╚═════╝
            {W}A U T O  –  F B
{W}─────────────────────────────────────────────{W}
{W}[{G}•{W}]{G} DEVELOPER {W}:{R} netz
{W}[{G}•{W}]{G} FACEBOOK  {W}:{R} netz
{W}[{G}•{W}]{G} GITHUB    {W}:{R} netz
{W}[{G}•{W}]{G} TOOL      {W}:{R} AUTO-FB
{W}─────────────────────────────────────────────{W}""")

def linex():
    print(f"{W}─────────────────────────────────────────────{W}")

oks = []
cps = []

def check_facebook_profile_picture(uid):
    pic_url = f"https://graph.facebook.com/{uid}/picture?type=normal"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36"
    }
    try:
        response = requests.get(pic_url, headers=headers, allow_redirects=False, timeout=10)
        if response.status_code == 302:
            redirect_url = response.headers.get("Location", "")
            if "scontent" in redirect_url:
                return "live"
            else:
                return "not_live"
        else:
            return
    except requests.RequestException as e:
        return 

def generate_yandex_alias(account_name):
    import time as _time
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', account_name.lower())
    timestamp = int(_time.time()) % 10000
    random_suffix = random.randint(100, 999)
    return f"{YANDEX_EMAIL.split('@')[0]}+{clean_name}{timestamp}{random_suffix}@yandex.com"

def createfb_method_1():
    global oks, cps
    banner()
    print(f"{W}[{G}1{W}]{G} FILIPINO NAMES")
    print(f"{W}[{G}2{W}]{G} RPW NAMES")
    linex()
    name_choice = input(f"{W}[{G}•{W}]{G} CHOISE {W}:{G} ")
    linex()
    num = int(input(f"{W}[{G}•{W}]{G} HOW MANY ACCOUNT {W}:{G} "))
    linex()
    print(f"{W}[{G}1{W}]{G} AUTO PASSWORD")
    print(f"{W}[{G}2{W}]{G} CUSTOM PASSWORD")
    linex()
    password_choice = input(f"{W}[{G}•{W}]{G} CHOISE {W}:{G} ")
    pww = get_pass() if password_choice == '1' else input(f"{W}[{G}•{W}]{G} ENTER PASSWORD {W}:{G} ")
    linex()
    show_details = input(f"{W}[{G}•{W}]{G} Show All Details y{R}/{G}n {W}:{G} ").lower()
    banner()
    print(f"{W}[{G}•{W}]{G} ACCOUNT CREATING STARTED")
    print(f'{W}[{G}•{W}]{G} TOTAL ID {W}: {R}{num}{W}')
    print(f"{W}[{G}•{W}]{G} Use {R}1.1.1{G} Vpn{W}")
    linex()

    import threading
    from concurrent.futures import ThreadPoolExecutor

    lock = threading.Lock()
    done = [0]

    def _create_one():
        while True:
            with lock:
                if done[0] >= num:
                    return
            try:
                ses = requests.Session()
                response = ses.get("https://x.facebook.com/reg", timeout=15)
                form = extractor(response.text)

                if not form.get("lsd") and not form.get("fb_dtsg"):
                    time.sleep(3)
                    continue

                firstname, lastname = get_rpw_name() if name_choice == '2' else get_bd_name()
                account_name = f"{firstname}{lastname}{random.randint(10, 999)}"
                email = generate_yandex_alias(account_name)

                payload = {
                    'ccp': "2",
                    'reg_instance': form.get("reg_instance", ""),
                    'submission_request': "true",
                    'reg_impression_id': form.get("reg_impression_id", ""),
                    'ns': "1",
                    'logger_id': form.get("logger_id", ""),
                    'firstname': firstname,
                    'lastname': lastname,
                    'birthday_day': str(random.randint(15, 25)),
                    'birthday_month': str(random.randint(5, 10)),
                    'birthday_year': str(random.randint(1985, 1995)),
                    'reg_email__': email,
                    'sex': "1",
                    'encpass': f'#PWD_BROWSER:0:{int(time.time())}:{pww}',
                    'submit': "Sign Up",
                    'fb_dtsg': form.get("fb_dtsg", ""),
                    'jazoest': form.get("jazoest", ""),
                    'lsd': form.get("lsd", "")
                }

                merged_headers = {
                    "Host": "m.facebook.com",
                    "Connection": "keep-alive",
                    "User-Agent": ugenX(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "en-US,en;q=0.9",
                    'referer': 'https://mbasic.facebook.com/reg/',
                    'sec-ch-ua': '',
                    'sec-ch-ua-mobile': '?1',
                    'sec-ch-ua-platform': 'Android',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'same-origin',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1',
                }

                reg_submit = ses.post("https://www.facebook.com/reg/submit/", data=payload, headers=merged_headers, timeout=20)
                login_coki = ses.cookies.get_dict()
                response_text = reg_submit.text

                if "checkpoint" in response_text.lower() or "confirm" in response_text.lower() or "code" in response_text.lower():
                    print(f"{Y}[!] Verification required for {email}, polling for OTP...{W}")
                    success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                    if success and uid:
                        coki = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                        with lock:
                            if done[0] >= num:
                                return
                            done[0] += 1
                            current = done[0]
                            oks.append(uid)
                            if show_details == 'y':
                                print(f"\n{W}[{G}•{W}] Name   : {G}{firstname} {lastname}{W}")
                                print(f"{W}[{G}•{W}] Email  : {G}{email}{W}")
                                print(f"{W}[{G}•{W}] OTP    : {G}{otp_code}{W}")
                                print(f"{W}[{G}•{W}] UID    : {G}{uid}{W}")
                                print(f"{W}[{G}•{W}] PASS   : {G}{pww}{W}")
                                print(f"{W}[{G}•{W}] COOKIES: {G}{coki}{W}")
                                print(f"{W}─────────────────────────────────────────────{W}")
                            else:
                                print(f"\n{G}CYBER-X{W}-{G}[OK] {current}/{num} | {uid} | {pww} | OTP:{otp_code}")
                            try:
                                with open('accounts.txt', 'a') as f:
                                    f.write(f"{uid}|{pww}|{email}|{coki}|OTP:{otp_code}\n")
                            except Exception:
                                pass
                    else:
                        with lock:
                            cps.append(email)
                        print(f"{R}[!] Verification failed for {email}{W}")
                
                elif "c_user" in login_coki:
                    uid = login_coki["c_user"]
                    coki = ";".join([f"{k}={v}" for k, v in login_coki.items()])
                    
                    time.sleep(3)
                    check_resp = ses.get("https://mbasic.facebook.com/me/", allow_redirects=True)
                    if "checkpoint" in check_resp.text.lower() or "confirm" in check_resp.text.lower():
                        print(f"{Y}[!] Post-creation verification needed, fetching OTP...{W}")
                        success, uid2, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                        if success and uid2:
                            uid = uid2
                            coki = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    
                    with lock:
                        if done[0] >= num:
                            return
                        done[0] += 1
                        current = done[0]
                        oks.append(uid)
                        if show_details == 'y':
                            print(f"\n{W}[{G}•{W}] Name   : {G}{firstname} {lastname}{W}")
                            print(f"{W}[{G}•{W}] Email  : {G}{email}{W}")
                            if 'otp_code' in locals() and otp_code:
                                print(f"{W}[{G}•{W}] OTP    : {G}{otp_code}{W}")
                            print(f"{W}[{G}•{W}] UID    : {G}{uid}{W}")
                            print(f"{W}[{G}•{W}] PASS   : {G}{pww}{W}")
                            print(f"{W}[{G}•{W}] COOKIES: {G}{coki}{W}")
                            print(f"{W}─────────────────────────────────────────────{W}")
                        else:
                            otp_display = f" | OTP:{otp_code}" if 'otp_code' in locals() and otp_code else ""
                            print(f"\n{G}CYBER-X{W}-{G}[OK] {current}/{num} | {uid} | {pww}{otp_display}")
                        try:
                            with open('accounts.txt', 'a') as f:
                                otp_part = f"|OTP:{otp_code}" if 'otp_code' in locals() and otp_code else ""
                                f.write(f"{uid}|{pww}|{email}|{coki}{otp_part}\n")
                        except Exception:
                            pass
                else:
                    pass
                    
            except Exception as e:
                time.sleep(2)

    WORKERS = 5
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_create_one) for _ in range(WORKERS)]
        for f in futures:
            f.result()
    
    print(' ')
    linex()
    print(f'{W}[{G}•{W}]{G} The process has completed')
    linex()
    print(f'{W}[{G}•{W}]{G} Total OK {W}: {G}{len(oks)}')
    print(f'{W}[{R}•{W}]{G} Total CP {W}: {R}{len(cps)}')
    linex()
    input(f'{W}[{G}•{W}]{G} Press Enter to go back to menu... {W}')

def register_account(domain_choice, name_option="1", gender_option="3", custom_pass=None, max_retries=5):
    for attempt in range(max_retries):
        try:
            ses = requests.Session()
            response = ses.get("https://x.facebook.com/reg", timeout=15)
            form = extractor(response.text)

            if not form.get("lsd") and not form.get("fb_dtsg"):
                time.sleep(3)
                continue

            if name_option == "2":
                firstname, lastname = get_rpw_name()
            else:
                if gender_option == "1":
                    firstname = random.choice(first_names_male)
                elif gender_option == "2":
                    firstname = random.choice(first_names_female)
                else:
                    firstname = random.choice(first_names_male + first_names_female)
                lastname = random.choice(surnames)

            if gender_option == "1":
                fb_sex = "2"
            elif gender_option == "2":
                fb_sex = "1"
            else:
                fb_sex = random.choice(["1", "2"])

            import time as _time
            account_name = f"{firstname}{lastname}{int(_time.time())}{random.randint(100, 999)}"
            email = generate_yandex_alias(account_name)
            pww = custom_pass if custom_pass else get_pass()

            payload = {
                'ccp': "2",
                'reg_instance': form.get("reg_instance", ""),
                'submission_request': "true",
                'reg_impression_id': form.get("reg_impression_id", ""),
                'ns': "1",
                'logger_id': form.get("logger_id", ""),
                'firstname': firstname,
                'lastname': lastname,
                'birthday_day': str(random.randint(15, 25)),
                'birthday_month': str(random.randint(5, 10)),
                'birthday_year': str(random.randint(1985, 1995)),
                'reg_email__': email,
                'sex': fb_sex,
                'encpass': f'#PWD_BROWSER:0:{int(_time.time())}:{pww}',
                'submit': "Sign Up",
                'fb_dtsg': form.get("fb_dtsg", ""),
                'jazoest': form.get("jazoest", ""),
                'lsd': form.get("lsd", ""),
            }

            headers = {
                "Host": "m.facebook.com",
                "Connection": "keep-alive",
                "User-Agent": ugenX(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                'referer': 'https://mbasic.facebook.com/reg/',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': 'Android',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'upgrade-insecure-requests': '1',
            }

            reg_submit = ses.post("https://www.facebook.com/reg/submit/", data=payload, headers=headers, timeout=20)
            login_coki = ses.cookies.get_dict()
            response_text = reg_submit.text
            response_lower = response_text.lower()

            if "c_user" in login_coki:
                time.sleep(3)
                check_resp = ses.get("https://mbasic.facebook.com/me/", allow_redirects=True)
                if "checkpoint" in check_resp.text.lower():
                    success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                    if success and uid:
                        cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                        return {
                            "name": f"{firstname} {lastname}",
                            "email": email,
                            "password": pww,
                            "uid": uid,
                            "cookies": cookie_str,
                            "session": ses,
                            "otp_fetched": True,
                            "otp_code": otp_code
                        }
                    else:
                        continue
                else:
                    cookie_str = ";".join([f"{k}={v}" for k, v in login_coki.items()])
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": login_coki["c_user"],
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": False,
                        "otp_code": None
                    }
            
            otp_keywords = ["checkpoint", "confirm", "code", "verification"]
            needs_otp = any(kw in response_lower for kw in otp_keywords)
            
            if needs_otp:
                success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                if success and uid:
                    cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": uid,
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": True,
                        "otp_code": otp_code
                    }
                else:
                    continue

        except Exception as e:
            print(f"[DEBUG] Registration error: {e}")
        
        time.sleep(2)
    
    return None

def confirm_account_with_otp(session, response_text, otp_code):
    try:
        soup = BeautifulSoup(response_text, 'html.parser')
        form = soup.find('form')
        if not form:
            return None
        
        action = form.get('action', '')
        if not action.startswith('http'):
            action = 'https://www.facebook.com' + action
        
        fields = {}
        for inp in form.find_all('input'):
            name = inp.get('name')
            value = inp.get('value', '')
            if name:
                fields[name] = value
        
        for key in ['code', 'confirm_code', 'n', 'otp', 'verification_code', 'confirmation_code']:
            if key in fields:
                fields[key] = otp_code
                break
        
        confirm_res = session.post(action, data=fields, timeout=15)
        cookies = session.cookies.get_dict()
        
        if 'c_user' in cookies:
            cookie_str = ";".join([f"{k}={v}" for k, v in cookies.items()])
            return {
                "uid": cookies["c_user"],
                "cookies": cookie_str,
                "session": session
            }
        return None
    except Exception as e:
        print(f"[DEBUG] OTP confirmation error: {e}")
        return None

def get_cookie_string(session):
    cookies = session.cookies.get_dict()
    return ";".join([f"{k}={v}" for k, v in cookies.items()])

# ============ TELEGRAM BOT KE LIYE REGISTER ACCOUNT FUNCTION ============
def register_account_for_bot(domain_choice="yandex", name_option="1", gender_option="3", custom_pass=None, max_retries=5):
    """Single account creation for Telegram bot - returns dict with all details"""
    import time as _time
    
    for attempt in range(max_retries):
        try:
            ses = requests.Session()
            response = ses.get("https://x.facebook.com/reg", timeout=15)
            form = extractor(response.text)

            if not form.get("lsd") and not form.get("fb_dtsg"):
                time.sleep(3)
                continue

            if name_option == "2":
                firstname, lastname = get_rpw_name()
            else:
                if gender_option == "1":
                    firstname = random.choice(first_names_male)
                elif gender_option == "2":
                    firstname = random.choice(first_names_female)
                else:
                    firstname = random.choice(first_names_male + first_names_female)
                lastname = random.choice(surnames)

            if gender_option == "1":
                fb_sex = "2"
            elif gender_option == "2":
                fb_sex = "1"
            else:
                fb_sex = random.choice(["1", "2"])

            account_name = f"{firstname}{lastname}{int(_time.time())}{random.randint(100, 999)}"
            email = generate_yandex_alias(account_name)
            pww = custom_pass if custom_pass else get_pass()

            payload = {
                'ccp': "2",
                'reg_instance': form.get("reg_instance", ""),
                'submission_request': "true",
                'reg_impression_id': form.get("reg_impression_id", ""),
                'ns': "1",
                'logger_id': form.get("logger_id", ""),
                'firstname': firstname,
                'lastname': lastname,
                'birthday_day': str(random.randint(15, 25)),
                'birthday_month': str(random.randint(5, 10)),
                'birthday_year': str(random.randint(1985, 1995)),
                'reg_email__': email,
                'sex': fb_sex,
                'encpass': f'#PWD_BROWSER:0:{int(_time.time())}:{pww}',
                'submit': "Sign Up",
                'fb_dtsg': form.get("fb_dtsg", ""),
                'jazoest': form.get("jazoest", ""),
                'lsd': form.get("lsd", ""),
            }

            headers = {
                "Host": "m.facebook.com",
                "Connection": "keep-alive",
                "User-Agent": ugenX(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "en-US,en;q=0.9",
                'referer': 'https://mbasic.facebook.com/reg/',
                'sec-ch-ua-mobile': '?1',
                'sec-ch-ua-platform': 'Android',
                'sec-fetch-dest': 'document',
                'sec-fetch-mode': 'navigate',
                'sec-fetch-site': 'same-origin',
                'upgrade-insecure-requests': '1',
            }

            reg_submit = ses.post("https://www.facebook.com/reg/submit/", data=payload, headers=headers, timeout=20)
            login_coki = ses.cookies.get_dict()
            response_text = reg_submit.text
            response_lower = response_text.lower()

            if "c_user" in login_coki:
                time.sleep(3)
                check_resp = ses.get("https://mbasic.facebook.com/me/", allow_redirects=True)
                if "checkpoint" in check_resp.text.lower():
                    success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                    if success and uid:
                        cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                        return {
                            "name": f"{firstname} {lastname}",
                            "email": email,
                            "password": pww,
                            "uid": uid,
                            "cookies": cookie_str,
                            "session": ses,
                            "otp_fetched": True,
                            "otp_code": otp_code
                        }
                    else:
                        continue
                else:
                    cookie_str = ";".join([f"{k}={v}" for k, v in login_coki.items()])
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": login_coki["c_user"],
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": False,
                        "otp_code": None
                    }
            
            otp_keywords = ["checkpoint", "confirm", "code", "verification"]
            needs_otp = any(kw in response_lower for kw in otp_keywords)
            
            if needs_otp:
                success, uid, cookies_dict, otp_code = confirm_account_with_auto_otp(ses, email)
                if success and uid:
                    cookie_str = ";".join([f"{k}={v}" for k, v in cookies_dict.items()])
                    return {
                        "name": f"{firstname} {lastname}",
                        "email": email,
                        "password": pww,
                        "uid": uid,
                        "cookies": cookie_str,
                        "session": ses,
                        "otp_fetched": True,
                        "otp_code": otp_code
                    }
                else:
                    continue

        except Exception as e:
            print(f"[DEBUG] Registration error: {e}")
        
        time.sleep(2)
    
    return None

def method():
    while True:
        banner()
        print(f"{W}[{G}1{W}]{G} Auto Create Fb ")
        linex()
        choice = input(f"{W}[{G}•{W}]{G} CHOISE {W}:{G} ").strip()
        if choice == '1':
            createfb_method_1()
        else:
            print(f"{R}Invalid choice!{W}")
            input(f"{W}[{G}•{W}]{G} Press Enter to continue ")

if __name__ == "__main__":
    sys.stdout.write('\x1b]2; CYBER-X\x07')
    install_dependencies()
    method()
