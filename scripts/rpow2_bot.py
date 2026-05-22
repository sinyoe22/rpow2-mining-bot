#!/usr/bin/env python3
"""
RPOW2 Mining Bot
Tribute to Hal Finney's original RPOW - automated mining bot
"""

import requests
import hashlib
import struct
import time
import json
import sys
from datetime import datetime

API_BASE = "https://api.rpow2.com"

class RPOW2Bot:
    def __init__(self, email: str):
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.mined_count = 0
        self.total_hashes = 0
        self.start_time = None
        
    def request_magic_link(self):
        """Request magic link for email login"""
        resp = self.session.post(f"{API_BASE}/auth/request", json={"email": self.email})
        data = resp.json()
        if "ok" in data:
            print(f"✅ Magic link sent to {self.email}")
            print(f"   Cooldown: {data.get('cooldown_seconds', '?')}s")
            return True
        elif "error" in data:
            print(f"❌ Error: {data.get('message', 'Unknown error')}")
            return False
        return False
    
    def verify_token(self, token: str):
        """Verify magic link token to get session"""
        resp = self.session.get(f"{API_BASE}/auth/verify", params={"token": token})
        data = resp.json()
        if "error" in data:
            print(f"❌ Verify error: {data.get('message')}")
            return False
        print("✅ Login successful!")
        return True
    
    def set_cookie(self, cookie_str: str):
        """Set session cookie manually (extracted from browser)"""
        # Parse cookie string like "session=abc123; other=value"
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                self.session.cookies.set(name.strip(), value.strip(), domain="api.rpow2.com")
    
    def get_me(self):
        """Get current user info"""
        try:
            resp = self.session.get(f"{API_BASE}/me")
            return resp.json()
        except:
            return None
    
    def get_challenge(self):
        """Get mining challenge from server"""
        resp = self.session.post(f"{API_BASE}/challenge")
        data = resp.json()
        if "error" in data:
            print(f"❌ Challenge error: {data.get('message')}")
            return None
        return data
    
    def submit_mint(self, challenge_id: str, solution_nonce: int):
        """Submit mining solution"""
        resp = self.session.post(f"{API_BASE}/mint", json={
            "challenge_id": challenge_id,
            "solution_nonce": str(solution_nonce)
        })
        return resp.json()
    
    @staticmethod
    def count_trailing_zero_bits(data: bytes) -> int:
        """Count trailing zero bits in byte array"""
        bits = 0
        for byte in reversed(data):
            if byte == 0:
                bits += 8
                continue
            b = byte
            while b & 1 == 0:
                bits += 1
                b >>= 1
            break
        return bits
    
    @staticmethod
    def hex_to_bytes(hex_str: str) -> bytes:
        """Convert hex string to bytes"""
        return bytes.fromhex(hex_str)
    
    def mine(self, nonce_prefix_hex: str, difficulty_bits: int) -> int:
        """
        Mine to find nonce with required trailing zero bits
        Returns the solution nonce
        """
        nonce_prefix = self.hex_to_bytes(nonce_prefix_hex)
        buffer = bytearray(nonce_prefix + b'\x00' * 8)
        
        nonce = 0
        hashes = 0
        start = time.time()
        last_report = start
        
        while True:
            struct.pack_into('<Q', buffer, len(nonce_prefix), nonce)
            digest = hashlib.sha256(buffer).digest()
            trailing_zeros = self.count_trailing_zero_bits(digest)
            
            if trailing_zeros >= difficulty_bits:
                elapsed = time.time() - start
                rate = hashes / elapsed if elapsed > 0 else 0
                print(f"\n🎯 FOUND SOLUTION!")
                print(f"   Nonce: {nonce}")
                print(f"   Trailing zeros: {trailing_zeros} (need {difficulty_bits})")
                print(f"   Hashes: {hashes:,}")
                print(f"   Time: {elapsed:.1f}s")
                print(f"   Rate: {rate:,.0f} H/s")
                return nonce
            
            nonce += 1
            hashes += 1
            
            now = time.time()
            if now - last_report >= 2:
                elapsed = now - start
                rate = hashes / elapsed if elapsed > 0 else 0
                print(f"\r⛏️  Mining... {hashes:,} hashes | {rate:,.0f} H/s | {elapsed:.0f}s", end="", flush=True)
                last_report = now
    
    def run(self):
        """Main mining loop"""
        print("=" * 60)
        print("  RPOW2 Mining Bot - Tribute to Hal Finney")
        print("=" * 60)
        
        me = self.get_me()
        if not me or "error" in me:
            print("\n❌ Not logged in!")
            print("Options:")
            print("1. python rpow2_bot.py --login  (send magic link)")
            print("2. python rpow2_bot.py --cookie 'session=abc123'  (use browser cookie)")
            return
        
        print(f"\n👤 Logged in as: {me.get('email', 'unknown')}")
        print(f"   Minted: {me.get('minted', 0)}")
        print(f"   Balance: {me.get('minted', 0) - me.get('sent', 0)}")
        
        self.start_time = time.time()
        
        print("\n🚀 Starting mining loop...")
        print("-" * 60)
        
        while True:
            try:
                challenge = self.get_challenge()
                if not challenge:
                    print("❌ Failed to get challenge, retrying in 5s...")
                    time.sleep(5)
                    continue
                
                challenge_id = challenge["challenge_id"]
                difficulty = challenge["difficulty_bits"]
                nonce_prefix = challenge["nonce_prefix"]
                
                print(f"\n📋 New challenge: {challenge_id[:16]}...")
                print(f"   Difficulty: {difficulty} trailing zero bits")
                
                solution = self.mine(nonce_prefix, difficulty)
                
                print(f"\n📤 Submitting solution...")
                result = self.submit_mint(challenge_id, solution)
                
                if "error" in result:
                    print(f"❌ Submit error: {result.get('message')}")
                    time.sleep(2)
                    continue
                
                self.mined_count += 1
                token_id = result.get("token", {}).get("id", "?")
                
                elapsed = time.time() - self.start_time
                rate = self.mined_count / (elapsed / 3600) if elapsed > 0 else 0
                
                print(f"✅ MINED #{self.mined_count}!")
                print(f"   Token: {token_id}")
                print(f"   Total mined: {self.mined_count}")
                print(f"   Avg rate: {rate:.1f}/hour")
                print("-" * 60)
                
            except KeyboardInterrupt:
                print(f"\n\n{'=' * 60}")
                print(f"  Mining stopped!")
                print(f"  Total mined: {self.mined_count}")
                print(f"  Total time: {(time.time() - self.start_time) / 3600:.1f} hours")
                print(f"{'=' * 60}")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                time.sleep(5)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RPOW2 Mining Bot")
    parser.add_argument("--email", default="[REDACTED_EMAIL]", help="Email for login")
    parser.add_argument("--login", action="store_true", help="Request magic link")
    parser.add_argument("--verify", help="Verify magic link token")
    parser.add_argument("--cookie", help="Set session cookie from browser")
    parser.add_argument("--status", action="store_true", help="Check account status")
    args = parser.parse_args()
    
    bot = RPOW2Bot(args.email)
    
    if args.login:
        bot.request_magic_link()
    elif args.verify:
        bot.verify_token(args.verify)
    elif args.cookie:
        bot.set_cookie(args.cookie)
        me = bot.get_me()
        if me and "error" not in me:
            print(f"✅ Cookie valid! Logged in as {me.get('email')}")
            print(f"   Minted: {me.get('minted', 0)}")
        else:
            print("❌ Invalid cookie")
    elif args.status:
        me = bot.get_me()
        if me and "error" not in me:
            print(f"👤 {me.get('email')}")
            print(f"   Minted: {me.get('minted', 0)}")
            print(f"   Sent: {me.get('sent', 0)}")
            print(f"   Received: {me.get('received', 0)}")
        else:
            print("❌ Not logged in")
    else:
        bot.run()


if __name__ == "__main__":
    main()
