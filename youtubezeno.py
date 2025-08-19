import os
import json
import sys
import string
import shutil
import asyncio
import threading
import yt_dlp
import tempfile
import time
import base64
import subprocess
import socket
import aiohttp
import aiofiles
from mutagen.mp3 import MP3
from collections import deque
import random
from datetime import datetime, timedelta

from highrise import BaseBot, __main__
from highrise.models import User, SessionMetadata, Position
from highrise import *
from highrise.webapi import *
from highrise.models_webapi import *
from highrise.models import *

from HRDB import ownerz, playlist, user_ticket, vip_users, msg, restrict, promo, bot_location, ids

invite = "675f21fcecbfd6b18c0474f3"

# Icecast server configuration - Zeno.fm ayarları
SERVER_HOST = "link.zeno.fm" # dont change.
SERVER_PORT = 80 # dont change
MOUNT_POINT = "/wrmddxrooeyvv" # mount point from your settings
STREAM_USERNAME = "source" # dont change
STREAM_PASSWORD = "dIL0u18k" # your mount password from settings

AUDIO_FILES = [
    "Nothing.mp3"
]

# Check if audio files exist, if not create a simple fallback
import os
if not os.path.exists("Nothing.mp3"):
    # Create a simple text file as placeholder for now
    with open("Nothing.mp3", "w") as f:
        f.write("# Placeholder audio file - replace with actual MP3")

class BotDefinition:
    def __init__(self, bot: BaseBot, room_id: str, api_token: str):
        self.bot = bot
        self.room_id = room_id
        self.api_token = api_token

class SEA(BaseBot):
    def __init__(self):
        super().__init__()
        self.message_task = None
        self.notification_task = None
        self.promo_task = None
        self.username = None
        self.owner_id = None
        self.owner = None
        self.bot_id = None
        self.skip = False
        self.bitrate = '128k'
        self.choices = {}
        self.req_files = deque()
        self.now = deque()
        self.message = deque()
        self.wait = []
        self.state_file = "bot_state.json"
        self.req_files_dir = "./reqfiles"
        self.fav_dir = "./fav"
        self.room_id = None  # Room ID'yi saklamak için
        os.makedirs(self.fav_dir, exist_ok=True)
        os.makedirs(self.req_files_dir, exist_ok=True)
        self.load_state()

        self.dance_loop_running = False

    def count_user_songs_in_queue(self, username):
        """Kullanıcının kuyruktaki şarkı sayısını hesapla"""
        count = 0
        for song in self.req_files:
            if song.get('user') == username:
                count += 1
        return count

    def save_state(self):
        """Save the current state of the req_files deque, with updated file paths."""
        try:
            data = {
                "req_files": [
                    {
                        "title": item["title"],
                        "url": item["url"],
                        "duration": item["duration"],
                        "user": item["user"]
                    }
                    for item in self.req_files
                ]
            }
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving state: {type(e).__name__} - {e}")

    def load_state(self):
        """Load the saved state of the req_files deque from a JSON file."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    self.req_files = deque(data.get("req_files", []))
                    os.remove(self.state_file)
            except Exception as e:
                print(f"Error loading state: {type(e).__name__} - {e}")

    def move_files_and_update_urls(self):
        for item in self.req_files:
            if item["url"].startswith("/tmp/"):
                temp_file_path = item["url"]
                new_file_path = os.path.join(self.req_files_dir, os.path.basename(temp_file_path))

                try:
                    shutil.move(temp_file_path, new_file_path)
                    item["url"] = new_file_path
                except Exception as e:
                    print(f"Error moving file {temp_file_path} to {new_file_path}: {type(e).__name__} - {e}")

    async def restart_bot(self):
        self.move_files_and_update_urls()
        self.save_state()
        await asyncio.sleep(5)
        os.execv(sys.executable, [sys.executable, 'run.py'] + sys.argv[1:])


    async def _dance_loop(self):
        """ تشغيل حلقة الرقص مع إعادة المحاولة عند فشل الاتصال """
        while self.dance_loop_running:
            try:
                await self.highrise.send_emote("emote-hyped")
                await asyncio.sleep(7.3)
            except Exception as e:
                break  #إذا كان الخطأ غير متوقع، نوقف الحلقة

    async def on_start(self, session_metadata: SessionMetadata):
        try:
            self.username = await self.get_username(session_metadata.user_id)
            self.bot_id = session_metadata.user_id
            self.owner_id = session_metadata.room_info.owner_id
            self.owner = await self.get_username(self.owner_id)
        except Exception as e:
            print("Error in get username, and bot id on start:", e)

        if not (self.owner is None):
            if self.owner not in ownerz:
                ownerz.append(self.owner)
            else:
                pass
        else:
            pass

        if not (self.owner_id is None):
            if self.owner_id not in msg:
                msg.append(self.owner_id)
            else:
                pass
        else:
            pass

        if bot_location:
            await self.highrise.teleport(session_metadata.user_id, Position(**bot_location))
            # تشغيل حلقة الرقص
            self.dance_loop_running = True
            self.dance_loop_task = asyncio.create_task(self._dance_loop())
        else:
            await self.highrise.teleport(session_metadata.user_id, Position(15.5, 0.25, 2.5, 'FrontRight'))
            # تشغيل حلقة الرقص
            self.dance_loop_running = True
            self.dance_loop_task = asyncio.create_task(self._dance_loop())

        if self.notification_task is None or self.notification_task.done():
            self.notification_task = asyncio.create_task(self.notification())
        else:
            pass

        if self.message_task is None or self.message_task.done():
            self.message_task = asyncio.create_task(self.print_messages())

        if self.promo_task is None or self.promo_task.done():
            self.promo_task = asyncio.create_task(self.promo())
        print(f"{self.username} is alive.")

    async def on_message(self, user_id: str, conversation_id: str, is_new_conversation: bool) -> None:
        try:
            response = await self.highrise.get_messages(conversation_id)
            if isinstance(response, GetMessagesRequest.GetMessagesResponse):
                message = response.messages[0].content
                if message != "/verify":
                    if user_id not in ids:
                        ids.append(user_id)
                    return
            username = await self.get_username(user_id)
            info = await self.webapi.get_user(user_id)
            joined_at = info.user.joined_at
            if isinstance(joined_at, datetime):
                one_month_ago = datetime.now(joined_at.tzinfo) - timedelta(days=30)
                if joined_at <= one_month_ago:
                    if not username in user_ticket:
                        user_ticket[username] = 3
                        await self.highrise.send_message(conversation_id, "Hesabınız doğrulandı.")
                        await self.highrise.send_message(conversation_id, "3 ücretsiz bilet aldınız!")
                        if not user_id in ids:
                            ids.append(user_id)
                else:
                    await self.highrise.send_message(conversation_id, "Hesabınız en az 30 gün eski olmalı.")
        except Exception as e:
            print(e)

    async def get_username(self, user_id):
        user_info = await self.webapi.get_user(user_id)
        return user_info.user.username

    async def invite_all(self, user):
        if not user.username in ownerz:
            await self.highrise.send_whisper(user.id, "Bu komutu kullanamazsınız.")
            return
        try:
            # Room ID'yi otomatik al
            invite_room = self.room_id if self.room_id else "675f21fcecbfd6b18c0474f3"
            for erm in ids:
                message_id = f"1_on_1:{erm}:{self.bot_id}"
                await self.highrise.send_message(
                    message_id,
                    message_type="invite",
                    content="Bu odaya katıl!",
                    room_id=invite_room)
                await asyncio.sleep(3)
        except Exception as e:
            await self.highrise.chat(f"Hata: {e}")

    async def color(self: BaseBot, category: str, color_palette: int):
        outfit = (await self.highrise.get_my_outfit()).outfit
        for outfit_item in outfit:
            item_category = outfit_item.id.split("-")[0]
            if item_category == category:
                try:
                    outfit_item.active_palette = color_palette
                except:
                    await self.highrise.chat(f"Bot '{category}' kategorisinden herhangi bir eşya kullanmıyor.")
                    return
        await self.highrise.set_outfit(outfit)

    async def equip(self, item_name: str):
        items = (await self.webapi.get_items(item_name=item_name)).items
        if not items:
            await self.highrise.chat(f"'{item_name}' eşyası bulunamadı.")
            return

        item = items[0]
        item_id, category = item.item_id, item.category

        inventory = (await self.highrise.get_inventory()).items
        has_item = any(inv_item.id == item_id for inv_item in inventory)

        if not has_item:
            if item.rarity == Rarity.NONE:
                pass
            elif not item.is_purchasable:
                await self.highrise.chat(f"'{item_name}' eşyası satın alınamaz.")
                return
            else:
                try:
                    response = await self.highrise.buy_item(item_id)
                    if response != "success":
                        await self.highrise.chat(f"'{item_name}' eşyası satın alınamadı.")
                        return
                    await self.highrise.chat(f"'{item_name}' eşyası satın alındı.")
                except Exception as e:
                    await self.highrise.chat(f"'{item_name}' satın alınırken hata: {e}")
                    return

        new_item = Item(
            type="clothing",
            amount=1,
            id=item_id,
            account_bound=False,
            active_palette=0,
        )

        outfit = (await self.highrise.get_my_outfit()).outfit
        outfit = [
            outfit_item
            for outfit_item in outfit
            if outfit_item.id.split("-")[0][0:4] != category[0:4]
        ]

        if category == "hair_front" and item.link_ids:
            hair_back_id = item.link_ids[0]
            hair_back = Item(
                type="clothing",
                amount=1,
                id=hair_back_id,
                account_bound=False,
                active_palette=0,
            )
            outfit.append(hair_back)
        outfit.append(new_item)
        await self.highrise.set_outfit(outfit)
    async def remove(self: BaseBot, category: str):
        outfit = (await self.highrise.get_my_outfit()).outfit

        for outfit_item in outfit:
            item_category = outfit_item.id.split("-")[0][0:3]
            if item_category == category[0:3]:
                try:
                    outfit.remove(outfit_item)
                except Exception as e:
                     pass
                     return
            await self.highrise.set_outfit(outfit)

    async def on_chat(self, user: User, message: str):
        if message.startswith("/remove"):
            if not user.username in ownerz:
                return
            try:
                parts = message.split()
                if len(parts) == 2:
                    _, category = parts
                    await self.remove(category)
                else:
                    await self.highrise.send_whisper(user.id, "Geçersiz format. Kullanım: /remove [eşya_adı]")
            except:
                pass

        if message.startswith("/equip"):
            if not user.username in ownerz:
                return
            try:
                parts = message.split()
                if len(message.split()) >= 2:
                    item_name = message.split(maxsplit=1)[1].strip()  # Get everything after /equip
                    await self.equip(item_name)
                else:
                    await self.highrise.send_whisper(user.id, "Geçersiz format. Kullanım: /equip [eşya_adı]")
            except:
                pass

        if message.startswith("/color"):
            if not user.username in ownerz:
                return
            parts = message.split()
            if len(parts) == 3:
                _, category, color_palette = parts
                try:
                    color_palette = int(color_palette)  # Convert to integer
                    await self.color(category, color_palette)
                except ValueError:
                    await self.highrise.send_whisper(user.id, "Renk paleti bir sayı olmalıdır.")
            else:
                await self.highrise.send_whisper(user.id, "Geçersiz format. Kullanım: /color [kategori] [palet_numarası]")

        if message.startswith("/invite"):
            try:
                await self.invite_all(user)
            except Exception as e:
                await self.highrise.chat(f"Sorun: {e}")
        if not message.lower() == "no":
            if not message.lower() == "yes":
                if user.username in self.choices:
                    try:
                        if not user.username in self.wait:
                            self.wait.append(user.username)
                            await self.highrise.send_whisper(user.id, "Değişiklikleri uygulamak için 'yes' veya 'no' yazın.")
                            await self.highrise.send_whisper(user.id, "10 saniye içinde 'yes' veya 'no' ile cevap vermezseniz işlem iptal edilir.")
                        await asyncio.sleep(10)
                        if user.username in self.choices:
                            del self.choices[user.username]
                            if user.username in self.wait:
                                self.wait.remove(user.username)
                            await self.highrise.send_whisper(user.id, "İşlem iptal edildi.")
                    except:
                        pass

        if message.lower() == "no":
            if user.username == "Atknz" or user.username in ownerz:
                if user.username in self.choices:
                    await self.highrise.send_whisper(user.id, "İşlem iptal edildi.")
                    del self.choices[user.username]

        if message.lower() == "yes":
            if user.username == "Atknz" or user.username in ownerz:
                if user.username in self.choices:
                    new_bitrate = self.choices[user.username]
                    self.bitrate = new_bitrate
                    await self.highrise.chat(f"Ses bit hızı başarıyla {new_bitrate} olarak güncellendi.")
                    del self.choices[user.username]

        if message.startswith("/cbit") and (user.username == "Atknz" or user.username in ownerz):
            await self.highrise.send_whisper(user.id, f"Şu anda ses {self.bitrate}bps hızında yayınlanıyor.")

        if message.startswith("/bitrate ") and (user.username == "Atknz" or user.username in ownerz):
            parts = message.split(" ")
            if len(parts) > 1:
                if parts[1].endswith("k") and parts[1][:-1].isdigit():
                    bitrate = parts[1]
                    await self.highrise.chat(f"Ses bit hızını {bitrate} olarak değiştirmek istediğinizden emin misiniz?")
                    await self.highrise.send_whisper(user.id, "Bu ses akışını etkileyebilir.\n"
"Onaylamak için 'yes', iptal etmek için 'no' yazın.")
                    self.choices[user.username] = bitrate
                else:
                    await self.highrise.send_whisper(user.id, "Geçersiz komut, kullanım: /bitrate [sayı]k\nÖrnek: /bitrate 256k")
            else:
                await self.highrise.send_whisper(user.id, "Geçersiz komut, kullanım: /bitrate [sayı]k\nÖrnek: /bitrate 128k")

        if message == "/restart" and (user.username == "Atknz" or user.username in ownerz):
            try:
                await self.highrise.send_whisper(user.id, "Bot yeniden başlatılıyor...")
                await self.restart_bot()
            except Exception as e:
                print("Error in /restart command: ", e)

        if message.startswith("/help"):
            try:
                await self.highrise.send_whisper(user.id,"\nMEVCUT KOMUTLAR:\n/play <şarkı adı> veya /play <youtube url> - Şarkı çal.\n/next - Sıradaki şarkıyı göster.\n/skip - Mevcut şarkıyı geç.\n/skip [numara] - Sıradaki şarkıyı geç.")
                await asyncio.sleep(3)
                await self.highrise.send_whisper(user.id, "\n/now - Şu anda çalan şarkıyı göster\n"
                                    "/dump [numara] - Sıradaki şarkı bilgisini al\n"
                                    "/wallet - Bilet bilginizi görün.\n"
                                    "/give @kullanıcı [numara] - Kullanıcıya bilet ver.")
                await asyncio.sleep(1)
                await self.highrise.send_whisper(user.id, "\n/rlist - Bilet fiyat listesini görün.\n/info @kullanıcı - Kullanıcının bilet bilgisini al.\n/fav - Favori çalma listesine ekle.\n/rfav [numara] favori çalma listesinden kaldır.\n/flist - Favori çalma listesini göster.")
                await asyncio.sleep(1)
                await self.highrise.send_whisper(user.id, "\n/cfav - Favori çalma listesini temizle.\n/transfer @kullanıcı [numara] - Biletlerinizi kullanıcıya transfer et (min 6 bilet)")
                return
            except:
                pass

        if message.startswith("/ahelp") and user.username in ownerz:
            try:
                await self.highrise.send_whisper(user.id,"\nADMİN KOMUTLARI:\n/add @kullanıcı - Kullanıcıyı sahiplere ekle\n/rem @kullanıcı - Kullanıcıyı sahiplerden kaldır\n/addv @kullanıcı - Kullanıcıyı VIP'e ekle\n/remv @kullanıcı - Kullanıcıyı VIP'ten kaldır")
                await asyncio.sleep(3)
                await self.highrise.send_whisper(user.id, "\n/give @kullanıcı [numara] - Kullanıcıya bilet ver\n/info @kullanıcı - Kullanıcının biletlerini kontrol et\n/res [şarkı] - Bir şarkıyı yasakla\n/unres [şarkı] - Şarkı yasağını kaldır")
                await asyncio.sleep(1)
                await self.highrise.send_whisper(user.id, "\n/promo [mesaj] - Promo mesajı ekle\n/rpromo [mesaj] - Promo mesajını kaldır\n/cpromo - Tüm promo mesajlarını temizle\n/msg @kullanıcı - Kullanıcıyı mesaj listesine ekle\n/rmsg @kullanıcı - Kullanıcıyı mesaj listesinden kaldır")
                await asyncio.sleep(1)
                await self.highrise.send_whisper(user.id, "\n/cmsg - Mesaj listesini temizle\n/vipz - Tüm VIP kullanıcıları listele\n/accs - Hesap istatistikleri\n/withdraw [miktar] - Altın çek\n/bwallet - Bot cüzdanını kontrol et")
                await asyncio.sleep(1)
                await self.highrise.send_whisper(user.id, "\n/setbot - Bot konumunu ayarla\n/base - Botu ayarlanan konuma taşı\n/bitrate [numara]k - Ses bit hızını değiştir\n/cbit - Mevcut bit hızını kontrol et\n/restart - Botu yeniden başlat")
                await asyncio.sleep(1)
                await self.highrise.send_whisper(user.id, "\n/equip [eşya] - Eşya giy\n/remove [kategori] - Eşya kategorisini kaldır\n/color [kategori] [palet] - Eşya rengini değiştir\n/invite - Tüm kullanıcıları davet et\n/fav - Mevcut şarkıyı favorilere ekle\n/rfav [numara] - Favorilerden kaldır\n/cfav - Favorileri temizle")
                return
            except:
                pass

        if message.startswith("/play"):
            if (user.username in vip_users) or (user.username in user_ticket and user_ticket[user.username] > 0) or (user.username in ownerz):
                try:
                    # Şarkı sınırlaması kontrolü
                    user_songs_count = self.count_user_songs_in_queue(user.username)

                    if user.username in ownerz:
                        # Ownerlar için sınırsız
                        pass
                    elif user.username in vip_users:
                        # VIPler için maksimum 2 şarkı
                        if user_songs_count >= 2:
                            await self.highrise.send_whisper(user.id, "VIP kullanıcılar aynı anda maksimum 2 şarkı açabilir. Mevcut şarkınız çalana kadar bekleyin.")
                            return
                    else:
                        # Normal kullanıcılar için maksimum 1 şarkı
                        if user_songs_count >= 1:
                            await self.highrise.send_whisper(user.id, "Aynı anda sadece 1 şarkı açabilirsiniz. Mevcut şarkınız çalana kadar bekleyin.")
                            return

                    query = message.split(" ", 1)[1]
                    lower_query = query.lower()
                    for item in restrict:
                        if item.lower() in lower_query:
                            await self.highrise.send_whisper(user.id, "Bu şarkı yasaklı. Biletiniz iade edildi.")
                            return
                    if query.startswith("https://"):
                        if "playlist" not in query:
                            await self.highrise.send_whisper(user.id, "Linkler şu an desteklenmiyor, şarkı - sanatçı olarak ekleyin.")
                            return
                            await self.highrise.send_whisper(user.id, "İsteğiniz işleniyor. Sabırlı olun.")
                            if user.username in user_ticket:
                                if user.username not in ownerz and user.username not in vip_users:
                                    await asyncio.sleep(1)
                                    await self.highrise.send_whisper(user.id, "• Not: İstekler 1 bilet maliyetindedir. Biletlerinizi boşa harcamayın. İstediğiniz şarkı bulunamazsa biletiniz cüzdanınıza iade edilir.")
                            await self.add_to_queue(query, user)
                        else:
                            await self.highrise.send_whisper(user.id, "\n Çalma listesi ekleyemezsiniz. Bir seferde bir şarkı isteyin")
                    else:
                        await self.highrise.send_whisper(user.id, "İsteğiniz işleniyor. Sabırlı olun.")
                        if user.username in user_ticket and user.username not in ownerz and user.username not in vip_users:
                            await asyncio.sleep(1)
                            await self.highrise.send_whisper(user.id, "• Not: İstekler 1 bilet maliyetindedir. Biletlerinizi boşa harcamayın. İstediğiniz şarkı bulunamazsa biletiniz cüzdanınıza iade edilir.")
                        await self.add_to_queue(query, user)
                except IndexError:
                    await self.highrise.send_whisper(user.id, "/play komutundan sonra bir şarkı adı belirtin.")
                except Exception as e:
                    print(f"Error in chat command: {e}")
            else:
                await self.highrise.send_whisper(user.id, "Yeterli biletiniz yok.")
                await asyncio.sleep(3)
                await self.highrise.send_whisper(user.id, "Fiyat listesini görmek için /rlist yazın.")

        if message.startswith("/rlist"):
            try:
                await self.highrise.send_whisper(user.id, f"\n • Not: Odada @{self.username}'a bahşiş verin,\n • 1 bilet 5g maliyetinde\n • 3 bilet 10g maliyetinde\n • 30 bilet 100g maliyetinde, vb.")
                await asyncio.sleep(2)
                await self.highrise.send_whisper(user.id, f"\n*NOT*: @{self.username}'a odada 1k bahşiş vererek VIP olabilirsiniz.")
                await asyncio.sleep(2)
                await self.highrise.send_whisper(user.id, "VIP kullanıcılar bilet olmadan şarkı isteyebilir. VIP kullanıcılar her ay VIP üyeliklerini yenilemelidir.")
            except Exception as e:
                print("Error in rlist:", e)

        if message.startswith("/dump "):
            try:
                index_str = message.split("/dump ")[1]
                index = int(index_str)
                if self.now and self.now[0]['url'] in self.req_files:
                    index -= 1
                if 0 <= index < len(self.req_files):
                    file_info = self.req_files[index]
                    now = file_info['title']
                    audio_length = file_info['duration']
                    if file_info.get('user'):
                        await self.highrise.send_whisper(
                            user.id,
                            f"🎵 {index + 1}: {now}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {audio_length}\n (@{file_info['user']} tarafından istendi)"
                        )
                    else:
                        await self.highrise.send_whisper(
                            user.id,
                            f"🎵 {now}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {audio_length}"
                        )
                else:
                    await self.highrise.send_whisper(user.id, f"Sırada {index} numaralı şarkı bulunamadı.")
            except ValueError:
                await self.highrise.send_whisper(user.id, "Geçersiz indeks formatı. /dump komutundan sonra geçerli bir numara verin.")
            except Exception as e:
                print(f"Error in /dump command: {e}")
                await self.highrise.send_whisper(user.id, "İstek işlenirken hata oluştu.")

        if message.startswith("/now"):
            try:
                if not self.now:
                    await self.highrise.send_whisper(user.id, "Şu anda hiçbir şey çalmıyor.")
                    return

                now_playing = self.now[0]
                now = self.now[0]['title']
                if self.now[0]['user']:
                    await self.highrise.send_whisper(user.id, f"🎵 Şu anda çalıyor: {now}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {self.now[0]['audio_length']}\n (@{now_playing['user']} tarafından istendi)")
                else:
                    await self.highrise.send_whisper(user.id, f"🎵 Şu anda çalıyor: {now}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {self.now[0]['audio_length']}")
            except IndexError:
                await self.highrise.send_whisper(user.id, "Şu anda hiçbir şey çalmıyor.")
            except Exception as e:
                print(f"Error in /now command: {e}")
                await self.highrise.send_whisper(user.id, "İstek işlenirken hata oluştu.")

        if message.startswith("/wallet"):
            try:
                if user.username in user_ticket:
                    if user_ticket[user.username] == 0:
                        await self.highrise.send_whisper(user.id, f"Cüzdanınızda hiç bilet kalmadı. Bilet almak için @{self.username}'a bahşiş verin.")
                        return
                    if user_ticket[user.username] == 1:
                        await self.highrise.send_whisper(user.id, f"Cüzdanınızda sadece {user_ticket[user.username]} bilet kaldı.")
                        return
                    await self.highrise.send_whisper(user.id, f"Cüzdanınızda toplam: {user_ticket[user.username]} bilet var.")
                else:
                    await self.highrise.send_whisper(user.id, "3 ücretsiz bilet almak için bu bota özel mesaj atın.")
            except Exception as e:
                print("The error occurred in wallet:", e)

        if message.startswith("/next"):
            try:
                if len(self.req_files) > 1:
                    next_file = self.req_files[1]
                    audio_length = (next_file['duration'])
                    next = next_file['title']
                    if next_file['user']:
                        await self.highrise.send_whisper(user.id, f"🎵 Sıradaki şarkı: {next}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {audio_length}\n (@{next_file['user']} tarafından istendi)")
                    else:
                        await self.highrise.send_whisper(user.id, f"🎵 Sıradaki şarkı: {next}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {audio_length}")
                else:
                    await self.highrise.send_whisper(user.id, "Sırada başka şarkı yok")
            except Exception as e:
                    print(f"Error in /next command: {e}")
                    await self.highrise.send_whisper(user.id, "Sıra kontrol edilirken hata")



        if message.startswith("/skip"):
            try:
                parts = message.split(" ")
                if len(parts) > 1 and parts[1].isdigit():
                    if int(parts[1]) == 0:
                        return
                    index = int(parts[1]) - 1

                    if self.now and self.now[0]['url'] in AUDIO_FILES:
                        adjusted_index = index
                    else:
                        adjusted_index = index + 1
                    if 0 <= adjusted_index < len(self.req_files):
                        removed_file = self.req_files[adjusted_index]
                        rem_length = self.req_files[adjusted_index]['duration']
                        req_user = self.req_files[adjusted_index]['user']
                        fix_rem = removed_file['title']
                        if not (user.username in ownerz or user.username == req_user):
                            await self.highrise.send_whisper(user.id, "NOT: Sadece istediğiniz şarkıyı geçebilirsiniz.")
                            return
                        if os.path.exists(self.req_files[adjusted_index]['url']):
                            os.remove(self.req_files[adjusted_index]['url'])
                        self.req_files.remove(removed_file)

                        await self.highrise.chat(f"🎵 Sıradan kaldırıldı: {fix_rem}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {rem_length}")
                    else:
                        await self.highrise.send_whisper(user.id, f"Sırada {get_ordinal(index + 1)} numaralı şarkı bulunamadı.")
                else:
                    if not self.now:
                        await self.highrise.send_whisper(user.id, "Şu anda hiçbir şey çalmıyor.")
                        return
                    rem_length = self.now[0]['audio_length']
                    removed_file = self.now[0]
                    req_user = self.now[0]['user']
                    fix_rem = removed_file['title']
                    if not (user.username in ownerz or user.username == req_user):
                        await self.highrise.send_whisper(user.id, "NOT: Sadece istediğiniz şarkıyı geçebilirsiniz.")
                        return
                    await self.highrise.chat(f"🎵 Geçiliyor {fix_rem}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {rem_length}")
                    await asyncio.sleep(3)
                    self.skip = True
            except Exception as e:
                print(f"Error in /skip command: {e}")
                await self.highrise.send_whisper(user.id, "Hiçbir şey çalmıyor.")

        if message.startswith("/queue"):
            try:
                if len(self.req_files) > 0:
                    if self.now and self.now[0]['url'] not in AUDIO_FILES:
                        global_index = 1
                    else:
                        global_index = 0

                    if len(self.req_files) == 1 and global_index == 1:
                        await self.highrise.send_whisper(user.id, "Sıra boş.")
                        return

                    message_content = ""
                    queue_number = 1

                    for _, file in enumerate(list(self.req_files)[global_index:], start=global_index):
                        item = f"{queue_number}. {file['title']}\n"
                        if len(message_content) + len(item) > 255:
                            await self.highrise.send_whisper(user.id, f"\n{message_content.strip()}")
                            message_content = item
                        else:
                            message_content += item
                        queue_number += 1

                    if message_content:
                        await self.highrise.send_whisper(user.id, f"\n{message_content.strip()}")
                else:
                    await self.highrise.send_whisper(user.id, "Sıra boş.")
            except Exception as e:
                print(f"Error in /queue command: {e}")
                await self.highrise.send_whisper(user.id, "Sıra kontrol edilirken hata.")

        if message.startswith("/info ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                info = message.split(" ", 1)[1]
                infol = info.replace("@", "")
                if infol in user_ticket and user_ticket[infol] > 0:
                    if user_ticket[infol] == 1:
                        await self.highrise.chat(f"Kullanıcı {info} sadece {user_ticket[infol]} bilete sahip.")
                    if user_ticket[infol] > 1:
                        await self.highrise.chat(f"Kullanıcı {info} sadece {user_ticket[infol]} bilete sahip.")
                else:
                    await self.highrise.chat(f"Kullanıcı {info} hiç bilete sahip değil.")
            except Exception as e:
                print(e)

        if message.startswith("/rem ") and user.username in ownerz:
            try:
                remvip = message.split(" ", 1)[1]
                rem = remvip.replace("@", "")
                if rem in ownerz:
                    ownerz.remove(rem)
                    await self.highrise.chat(f"{remvip} sahiplerden kaldırıldı.")
                else:
                    await self.highrise.send_whisper(user.id, f"{rem} sahipler arasında değil.")
            except:
                pass

        if message.startswith("/add ") and user.username in ownerz:
            try:
                vip = message.split(" ", 1)[1]
                allowed = vip.replace("@", "")
                if allowed not in ownerz:
                    ownerz.append(allowed)
                    await self.highrise.chat(f"{vip} sahiplere eklendi.")
                else:
                    await self.highrise.chat(f"{vip} zaten sahip.")
            except:
                await self.highrise.send_whisper(user.id, "Hayır")

        if message.startswith("/vipz") and (user.username in ownerz or user.username == "Atknz"):
            try:
                if vip_users:
                    message_content = ""
                    for idx, user_name in enumerate(vip_users, start=1):
                        item = f"{idx}. {user_name}\n"
                        if len(message_content) + len(item) > 255:
                            await self.highrise.send_whisper(user.id, f"\n{message_content.strip()}")
                            message_content = item
                        else:
                            message_content += item
                    if message_content:
                        await self.highrise.send_whisper(user.id, f"\n{message_content.strip()}")
                else:
                    await self.highrise.send_whisper(user.id, "VIP listesi boş.")
            except Exception as e:
                print(f"Error in /vipz command: {e}")
                await self.highrise.send_whisper(user.id, "Sıra kontrol edilirken hata.")

        if message.startswith("/remv ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                current_date = datetime.now().strftime("%d/%m/%Y")
                remvip = message.split(" ", 1)[1]
                rem = remvip.replace("@", "")
                if rem in vip_users:
                    vip_users.remove(rem)
                    await self.highrise.chat(f"{remvip} VIP'ten kaldırıldı.")
                    for user_id in msg:
                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                        try:
                            await self.highrise.send_message(message_id, f"Kullanıcı {remvip} {current_date} tarihinde VIP'ten kaldırıldı, @{user.username} tarafından kaldırıldı")
                            await asyncio.sleep(1)
                        except Exception as e:
                            await self.highrise.chat(f"{user_id}'ye mesaj gönderilemedi: {e}")
                            print("Error in sending msg in /addv:", e)
                else:
                    await self.highrise.send_whisper(user.id, f"{rem} VIP değil.")
            except:
                pass

        if message.startswith("/addv ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                current_date = datetime.now().strftime("%d/%m/%Y")
                vip = message.split(" ", 1)[1]
                allowed = vip.replace("@", "")
                if allowed not in vip_users:
                    vip_users.append(allowed)
                    await self.highrise.chat(f"{vip} VIP'e eklendi.")
                    for user_id in msg:
                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                        try:
                            await self.highrise.send_message(message_id, f"Kullanıcı {vip} {current_date} tarihinde VIP oldu, @{user.username} tarafından eklendi")
                            await asyncio.sleep(1)
                        except Exception as e:
                            await self.highrise.chat(f"{user_id}'ye mesaj gönderilemedi: {e}")
                            print("Error in sending msg in /addv:", e)
                else:
                    await self.highrise.chat(f"{vip} zaten VIP.")
            except:
                await self.highrise.send_whisper(user.id, "Hayır")

        if message.startswith("/transfer"):
            try:
                _, username, value = message.split(" ", 2)
                username = username.strip("@")
                value = int(value)
                if not value >= 6:
                    await self.highrise.send_whisper(user.id, "NOT: En az 6 bilet transfer etmeniz gerekiyor.")
                else:
                    if user_ticket[user.username] >= value:
                        user_ticket[username] += value
                        user_ticket[user.username] -= value
                        await self.highrise.chat(f"{username}'a {value} bilet gönderildi.")
                    else:
                        await self.highrise.send_whisper(user.id, "Yeterli biletiniz yok")
            except Exception as e:
                print(f"An error occurred: {e}")

        if message.startswith("/give") and (user.username in ownerz or user.username == "Atknz"):
            try:
                _, username, value = message.split(" ", 2)
                username = username.strip("@")
                value = int(value)
                user_ticket[username] += value
                if value == 1:
                    await self.highrise.chat(f"{username}'a {value} bilet gönderildi.")
                    return
                await self.highrise.chat(f"{username}'a {value} bilet gönderildi.")
            except Exception as e:
                print(f"An error occurred: {e}")

        if message.startswith("/rfav ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                parts = message.split(" ")
                if len(parts) > 1 and parts[1].isdigit():
                    index = int(parts[1]) - 1
                    if 0 <= index <= len(playlist):
                        removed_file = playlist[index]
                        rem_length = removed_file.get('audio_length', 'Bilinmeyen süre')
                        fix_rem = removed_file.get('title', 'Bilinmeyen başlık')
                        file_path = removed_file.get('url', '')
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                            playlist.pop(index)

                            await self.highrise.chat(f"🎵 Sıradan kaldırıldı: {fix_rem}\n🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {rem_length}")
                    else:
                        await self.highrise.send_whisper(user.id, f"Sırada {get_ordinal(parts[1])} konumunda şarkı bulunamadı.")
                else:
                    await self.highrise.send_whisper(user.id, "Kaldırmak için geçerli bir şarkı numarası verin.")
            except Exception as e:
                print(f"Error in /rfav command: {e}")
                await self.highrise.send_whisper(user.id, f"Hata: {e}")

        if message.startswith("/flist"):
            try:
                if playlist:
                    message_content = ""
                    for idx, file in enumerate(list(playlist), start=1):
                        item = f"{idx}. {file['title']}\n"
                        if len(message_content) + len(item) > 255:
                            await self.highrise.send_whisper(user.id, f"\n{message_content.strip()}")
                            message_content = item
                        else:
                            message_content += item
                    if message_content:
                        await self.highrise.send_whisper(user.id, f"\n{message_content.strip()}")
                else:
                    await self.highrise.send_whisper(user.id, "Sıra boş.")
            except Exception as e:
                print(f"Error in /flist command: {e}")
                await self.highrise.send_whisper(user.id, "Sıra kontrol edilirken hata.")

        if message.startswith("/fav") and (user.username in ownerz or user.username == "Atknz"):
            try:
                if self.now:
                    fav = self.now[0]
                    if any(item['url'] == fav['url'] for item in playlist):
                        await self.highrise.chat(f"{fav['title']} zaten favori çalma listesinde.")
                        return
                    if fav['url'] in AUDIO_FILES:
                        await self.highrise.send_whisper(user.id, "• Not: Sadece istenen şarkıları favorilere ekleyebilirsiniz.")
                    else:
                        permanent_file = f"./fav/{fav['title']}.mp3"
                        try:
                            shutil.copy(fav['url'], permanent_file)
                        except Exception as e:
                            print("Error in /fav copy:", e)
                            return
                        fav['url'] = permanent_file
                        playlist.append(fav)
                        await self.highrise.chat(f"{fav['title']} favori çalma listesine eklendi.")
                else:
                    await self.highrise.chat("Şu anda hiçbir şey çalmıyor.")
            except Exception as e:
                print("Error in /fav command:", e)

        if message.startswith("/cfav"):
            if user.username in ownerz or user.username == "Atknz":
                if playlist:
                    for item in playlist:
                        if os.path.exists(item['url']):
                            try:
                                os.remove(item['url'])
                            except:
                                print("Error in /cfav for loop:", e)
                    playlist.clear()
                    await self.highrise.chat("Favori çalma listesi temizlendi.")
                else:
                    await self.highrise.chat("Favori çalma listesi zaten boş.")
            else:
                await self.highrise.send_whisper(user.id, "Bu komuta erişiminiz yok.")

        if message.startswith("/cmsg") and (user.username in ownerz or user.username == "Atknz"):
            try:
                if msg:
                    msg.clear()
                    await self.highrise.chat("Mesaj listesi temizlendi.")
                else:
                    await self.highrise.chat("Mesaj listesi zaten boş.")
            except:
                print("Error in /cmsg:", e)

        if message.startswith("/rmsg ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                user = message.split(" ", 1)[1]
                username = user.replace("@", "")
                room_users = (await self.highrise.get_room_users()).content
                user_id = None
                for user in room_users:
                    if user[0].username.lower() == username.lower():
                        user_id = user[0].id
                        break
                if user_id is None:
                    await self.highrise.send_whisper(user.id,"Kullanıcı odada bulunamadı.")
                    return
                if user_id in msg:
                    msg.remove(user_id)
                    await self.highrise.chat(f"Kullanıcı @{username} mesaj listesinden kaldırıldı.")
                else:
                    await self.highrise.chat("Kullanıcı listede değil.")
            except Exception as e:
                    print("Error in /rmsg:", e)

        if message.startswith("/msg ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                user = message.split(" ", 1)[1]
                username = user.replace("@", "")
                room_users = (await self.highrise.get_room_users()).content
                user_id = None
                for user in room_users:
                    if user[0].username.lower() == username.lower():
                        user_id = user[0].id
                        break
                if user_id is None:
                    await self.highrise.send_whisper(user.id,"Kullanıcı odada bulunamadı.")
                    return
                if user_id not in msg:
                    msg.append(user_id)
                    await self.highrise.chat(f"Kullanıcı @{username} mesaj listesine eklendi.")
                else:
                    await self.highrise.chat("Kullanıcı zaten listede.")
            except Exception as e:
                    print("Error in /msg:", e)

        if message.startswith("/res ") and user.username in ownerz:
            try:
                res = message.split(" ", 1)[1]
                if not res in restrict:
                    restrict.append(res)
                    await self.highrise.chat("Bu şarkı yasaklı şarkılara eklendi.")
                else:
                    await self.highrise.chat("Bu şarkı zaten yasaklı.")
            except Exception as e:
                print(f"Error in /restrict command: {e}")

        if message.startswith("/unres ") and user.username in ownerz:
            try:
                res = message.split(" ", 1)[1]
                if res in restrict:
                    restrict.remove(res)
                    await self.highrise.chat("Bu şarkı yasaklı şarkılar listesinden kaldırıldı.")
                else:
                    await self.highrise.chat("Bu şarkı yasaklı değil.")
            except Exception as e:
                print(f"Error in /unrestrict command: {e}")

        if message.startswith("/promo ") and user.username in ownerz:
            try:
                prom = message.lstrip("/promo ").strip()
                if prom:
                    if prom not in promo:
                        promo.append(prom)
                        await self.highrise.chat("Bu mesaj promo listesine eklendi.")
                    else:
                        await self.highrise.chat("Bu mesaj zaten promo listesinde.")
                else:
                    await self.highrise.chat("/promo komutundan sonra bir promosyon mesajı verin.")
            except Exception as e:
                print(f"Error in /promo command: {e}")

        if message.startswith("/rpromo ") and user.username in ownerz:
            try:
                prom = message.lstrip("/promo ").strip()
                if prom:
                    if prom in promo:
                        promo.remove(prom)
                        await self.highrise.chat("Bu mesaj promo listesinden kaldırıldı.")
                    else:
                        await self.highrise.chat("Bu mesaj promo listesinde değil.")
                else:
                    await self.highrise.chat("/promo komutundan sonra bir promosyon mesajı verin.")
            except Exception as e:
                print(f"Error in /rpromo command: {e}")

        if message.startswith("/cpromo"):
            try:
                if user.username == "Atknz" or user.username in ownerz:
                    if promo:
                        promo.clear()
                        await self.highrise.chat("Promo listesi temizlendi.")
                    else:
                        await self.highrise.chat("Promo listesi zaten boş.")
                else:
                    pass
            except:
                pass

        if message.startswith("/accs") and user.username in ownerz:
            try:
                total = len(user_ticket)
                empty = {key: value for key, value in user_ticket.items() if value == 0}
                active = {key: value for key, value in user_ticket.items() if value > 0 and value != 3}
                total_empty = len(empty)
                total_active = len(active)
                await self.highrise.chat(f"\nToplam {total} kullanıcı var, {total_active} aktif hesap, sadece {total_empty} kullanıcının bakiyesi 0.")
            except Exception as e:
                print("Error in /accs:", e)

        if message.startswith("/withdraw ") and (user.username in ownerz or user.username == "Atknz"):
            try:
                parts = message.split(" ")
                if len(parts) != 2:
                    await self.highrise.send_whisper(user.id, "\nKullanım: /withdraw [numara].")
                    return
                try:
                    amount = int(parts[1])
                except:
                    await self.highrise.send_whisper(user.id, "Ondalık sayılar ve kesirler kullanmayın, sadece tam sayılar [numara].")
                    return
                bot_wallet = await self.highrise.get_wallet()
                bot_amount = bot_wallet.content[0].amount
                if bot_amount <= amount:
                    await self.highrise.send_whisper(user.id, "Efendim, yeterli bakiyem yok.")
                    return
                """Possible values are: "gold_bar_1",
            "gold_bar_5", "gold_bar_10", "gold_bar_50",
            "gold_bar_100", "gold_bar_500",
            "gold_bar_1k", "gold_bar_5000", "gold_bar_10k" """
                bars_dictionary = {10000: "gold_bar_10k",
                               5000: "gold_bar_5000",
                               1000: "gold_bar_1k",
                               500: "gold_bar_500",
                               100: "gold_bar_100",
                               50: "gold_bar_50",
                               10: "gold_bar_10",
                               5: "gold_bar_5",
                               1: "gold_bar_1"}
                fees_dictionary = {10000: 1000,
                               5000: 500,
                               1000: 100,
                               500: 50,
                               100: 10,
                               50: 5,
                               10: 1,
                               5: 1,
                               1: 1}
                tip = []
                total = 0
                for bar in bars_dictionary:
                    if amount >= bar:
                        bar_amount = amount // bar
                        amount = amount % bar
                        for i in range(bar_amount):
                            tip.append(bars_dictionary[bar])
                            total = bar+fees_dictionary[bar]
                if total > bot_amount:
                    await self.highrise.send_whisper(user.id, "Efendim, yeterli fonlarım yok.")
                    return
                tip_string = ",".join(tip)
                await self.highrise.tip_user(user.id, tip_string)
            except Exception as e:
                print("Error in /withdraw:", e)

        if message == "/setbot" and user.username in ownerz:
            try:
                room_users = await self.highrise.get_room_users()
                for room_user, pos in room_users.content:
                    if room_user.username == user.username:
                        bot_location["x"] = pos.x
                        bot_location["y"] = pos.y
                        bot_location["z"] = pos.z
                        bot_location["facing"] = pos.facing
                        await self.highrise.send_whisper(user.id, f"Bot konumu şuna ayarlandı: {bot_location}")
                        break
            except Exception as e:
                print("Set bot:", e)

        if message == "/base" and user.username in ownerz:
            try:
                if bot_location:
                    await self.highrise.walk_to(Position(**bot_location))
            except Exception as e:
                print("Error in /base:", e)

        if message.startswith("/bwallet"):
            try:
                await self.bot_wallet(user, message)
            except:
                pass

    async def bot_wallet(self, user: User, message: str):
        if user.username in ownerz or user.username == "Atknz":
            wallet = await self.highrise.get_wallet()
            for item in wallet.content:
                if item.type == "gold":
                    gold = item.amount
                    await self.highrise.send_whisper(user.id, f"Efendim, mevcut bakiyem {gold} altın!")
                    return
            await self.highrise.send_whisper(f"Merhaba, {user.username}! Hiç altınım yok.")
        else:
            await self.highrise.send_whisper(user.id, "Bu komuta erişiminiz yok")

    async def on_user_join(self, user: User, pos: Position) -> None:
        try:
            response = await self.webapi.get_user(user.id)
            joined_at = response.user.joined_at

            if isinstance(joined_at, datetime):
                one_month_ago = datetime.now(joined_at.tzinfo) - timedelta(days=30)
                if joined_at <= one_month_ago:
                    if not user.username in user_ticket:
                        await self.highrise.send_whisper(user.id, "Odaya hoş geldiniz <3.\nÜcretsiz bilet almak için bu bota /verify yazın. Her şarkı isteği 1 bilet maliyetindedir.")
                        await asyncio.sleep(2)
                        await self.highrise.send_whisper(user.id, "Şarkı istemek için /play 'şarkı' yazın. Tüm komutlar için /help yazın.")
                        await asyncio.sleep(1)
                        await self.highrise.send_whisper(user.id, "Bot arıza yaparsa @Atknz'ye mesaj atın")
                    else:
                        await self.highrise.send_whisper(user.id, "Odaya tekrar hoş geldiniz <3.\nBilet bilginizi öğrenmek için /wallet yazın. Tüm komutlar için /help yazın.")
                        await asyncio.sleep(2)
                        await self.highrise.send_whisper(user.id, "Bot arıza yaparsa @Atknz'ye mesaj atın")
                else:
                    await self.highrise.send_whisper(user.id, "Odaya hoş geldiniz <3.\nBu bir müzik botudur. Fiyat listesi için /rlist yazın, her şarkı isteği 1 bilet maliyetindedir. Bilet bilginizi öğrenmek için /wallet yazın. Şarkı istemek için /play yazın.")
                    await asyncio.sleep(2)
                    await self.highrise.send_whisper(user.id, "Bot arıza yaparsa @Atknz'ye mesaj atın")
            else:
                pass
        except:
            pass

    async def on_tip(self, sender: User, receiver: User, tip: CurrencyItem | Item) -> None:
        try:
            if tip.amount == 1 and receiver.username == self.username:
                if sender.username in vip_users:
                    await self.highrise.send_whisper(sender.id, "Zaten VIP'siniz, bilete ihtiyacınız yok.")
                else:
                    await self.highrise.send_whisper(sender.id, "Bilet almak için en az 5g bahşiş verin.")

            elif tip.amount == 5 and receiver.username == self.username:
                user_ticket[sender.username] = user_ticket.get(sender.username, 0) + 1
                if sender.username in vip_users:
                    await self.highrise.send_whisper(sender.id, "Zaten VIP'siniz, bilete ihtiyacınız yok.")
                else:
                    await self.highrise.chat(f"{sender.username}'ın cüzdanı 5g bahşiş için 2 bilet ile güncellendi.")
                    await self.highrise.send_whisper(sender.id, f"Cüzdanınızdaki toplam bilet: {user_ticket[sender.username]}")

            elif tip.amount == 10 and receiver.username == self.username:
                user_ticket[sender.username] = user_ticket.get(sender.username, 0) + 3
                if sender.username in vip_users:
                    await self.highrise.send_whisper(sender.id, "Zaten VIP'siniz, bilete ihtiyacınız yok.")
                else:
                    await self.highrise.chat(f"{sender.username}'ın cüzdanı 10g bahşiş için 3 bilet ile güncellendi.")
                    await self.highrise.send_whisper(sender.id, f"Cüzdanınızdaki toplam bilet: {user_ticket[sender.username]}")

            elif tip.amount == 1000 and receiver.username == self.username:
                current_date = datetime.now().strftime("%d/%m/%Y")
                day = datetime.now().strftime("%d")
                if sender.username in vip_users:
                    await self.highrise.send_whisper(user.id, "VIP döneminiz uzatıldı. Altın bahşiş için teşekkürler. <3")
                    for user_id in msg:
                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                        try:
                            await self.highrise.send_message(message_id, f"Kullanıcı @{sender.username} {current_date} tarihinde 1000g bahşiş verdi.")
                            await asyncio.sleep(1)
                        except Exception as e:
                            print("Error in sending msg abt tip:", e)

                else:
                    vip_users.append(sender.username)
                    await self.highrise.send_whisper(user.id, "VIP kullanıcılara eklendiniz. Hata yaşarsanız @Atknz'ye mesaj atın. Keyfini çıkarın <3")
                    await self.highrise.send_whisper(user.id, f"\n*NOT*: VIP'iniz {current_date} tarihinden başladı, gelecek ayın {get_ordinal(day)}'ından önce VIP'inizi yenilediğinizden emin olun.")
                    for user_id in msg:
                        message_id = f"1_on_1:{user_id}:{self.bot_id}"
                        try:
                            await self.highrise.send_message(message_id, f"Kullanıcı @{sender.username} {current_date} tarihinde VIP oldu.")
                            await asyncio.sleep(1)
                        except Exception as e:
                            print("Error in sending msg abt tip:", e)

            elif tip.amount % 10 == 0 and tip.amount >= 10 and receiver.username == self.username:
                tickets = (tip.amount // 10) * 3
                user_ticket[sender.username] = user_ticket.get(sender.username, 0) + tickets
                await self.highrise.chat(f"{sender.username}'ın cüzdanı {tip.amount}g bahşiş için {tickets} bilet ile güncellendi.")
                await self.highrise.send_whisper(sender.id, f"Cüzdanınızdaki toplam bilet: {user_ticket[sender.username]}")
            else:
                pass
        except Exception as e:
            print(e)
            await self.highrise.send_whisper(sender.id, f"Hata oluştu: {e}. Lütfen @Atknz'yi bilgilendirin")

    async def add_to_queue(self, query, user):
        """Search for a song and add it to the queue using yt-dlp."""
        buffered_file_path, track_duration, track = await self.search_track(query, user)
        if buffered_file_path:
            self.req_files.append({
                'url': buffered_file_path,
                'title': track['title'],
                'uploader': track['uploader'],
                'duration': track_duration,
                'user': user.username,
            })
            await self.highrise.chat(f'🎵 {track["title"]}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• ({track_duration}) sıraya eklendi\n (@{user.username} tarafından istendi)')
            if user.username in user_ticket:
                if user.username not in ownerz:
                    if user.username not in vip_users:
                        user_ticket[user.username] -= 1
                        await self.highrise.send_whisper(user.id, f"Cüzdanınızda kalan bilet: {user_ticket[user.username]}")
        else:
            await asyncio.sleep(2)
            await self.highrise.send_whisper(user.id, "Şarkınız eklenemedi. Zaten sırada olan şarkıyı tekrar istememek ve 8 dakikadan uzun şarkı istememek için dikkat edin.")
            await asyncio.sleep(2)
            await self.highrise.send_whisper(user.id, "Biletiniz cüzdanınıza iade edildi. Tekrar deneyin.")

    async def download_chunk(self, session, url, start, end, queue):
        headers = {'Range': f'bytes={start}-{end}'}
        async with session.get(url, headers=headers) as response:
            if response.status not in [206, 200]:
                print(f"Failed to download chunk: {response.status}")
                await queue.put(None)
                return

            chunk = await response.content.read()
            await queue.put((start, chunk))

    async def download_audio(self, session, audio_url, download_queue):
        retries = 3
        for attempt in range(retries):
            async with session.head(audio_url) as response:
                if response.status == 302:
                    audio_url = response.headers['Location']
                    continue
                if response.status != 200:
                    print(f"Failed to get audio info: {response.status}")
                    await download_queue.put(None)
                    return
                break
            asyncio.sleep(1)
        else:
            print("Failed to get audio info after retries")
            await download_queue.put(None)
            return

        total_size = int(response.headers.get('Content-Length'))
        chunk_size = total_size // 4  # Download in 4 chunks

        tasks = []
        for i in range(4):
            start = i * chunk_size
            end = (i + 1) * chunk_size - 1 if i != 3 else total_size - 1
            tasks.append(self.download_chunk(session, audio_url, start, end, download_queue))

        await asyncio.gather(*tasks)
        await download_queue.put(None)

    async def write_audio(self, temp_file_path, download_queue, buffer_queue):
        buffer_size = 10 * 1024 * 1024  # 10 MB buffer size

        async with aiofiles.open(temp_file_path, 'wb') as temp_file:
            while True:
                item = await download_queue.get()
                if item is None:
                    break
                start, chunk = item
                await temp_file.seek(start)
                await temp_file.write(chunk)
                await buffer_queue.put(chunk)
                download_queue.task_done()

            await buffer_queue.put(None)

    async def buffer_audio(self, audio_url):
        async with aiohttp.ClientSession() as session:
            try:
                temp_file_path = tempfile.mktemp(suffix='.mp3')
                download_queue = asyncio.Queue()
                buffer_queue = asyncio.Queue()

                download_task = asyncio.create_task(self.download_audio(session, audio_url, download_queue))
                write_task = asyncio.create_task(self.write_audio(temp_file_path, download_queue, buffer_queue))

                await asyncio.sleep(1)
                await asyncio.gather(download_task, write_task)
                return temp_file_path

            except Exception as e:
                print(f"Buffering error: {e}")
                return None

    async def search_track(self, query, user):
        """Search for a track using yt-dlp and buffer the audio."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'ytsearch1',
            'max_downloads': 1,
            'match_filter': yt_dlp.utils.match_filter_func('duration > 10 & duration < 480 & view_count > 1000'),  # 8 dakika = 480 saniye
            'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
        }



        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if query.startswith("http"):
                    info = ydl.extract_info(query, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]

                track_url = info['url']
                track_duration = f"{info['duration'] // 60}:{info['duration'] % 60:02d}"
                track = {
                    "title": info['title'],
                    "uploader": info['uploader']
                }
                for items in self.req_files:
                    if items["title"] == info['title']:
                        await self.highrise.send_whisper(user.id, "Şarkı zaten sırada.")
                        return None, None, None

                attempts = 0
                while attempts < 3:
                    buffered_file_path = await self.buffer_audio(track_url)
                    if buffered_file_path is None:
                        attempts += 1
                        await asyncio.sleep(1)
                        continue

                    try:
                        file_size = os.path.getsize(buffered_file_path)
                        if file_size >= 4 * 1024:
                            break
                    except FileNotFoundError:
                        attempts += 1
                        await asyncio.sleep(1)
                        continue
                    attempts += 1
                    await asyncio.sleep(1)
                else: # If loop finishes without break
                    if buffered_file_path and os.path.exists(buffered_file_path):
                        os.remove(buffered_file_path) # Clean up if it exists but is too small
                    return None, None, None

                if os.path.getsize(buffered_file_path) >= 4 * 1024:
                    return buffered_file_path, track_duration, track
                else:
                    if buffered_file_path and os.path.exists(buffered_file_path):
                        os.remove(buffered_file_path)
                    return None, None, None
        except Exception as e:
            print(f"Error searching track: {e}")
            return None, None, None

    async def promo(self):
        while True:
            try:
                for items in promo:
                    await self.highrise.chat(items)
                    await asyncio.sleep(100)
                else:
                    await asyncio.sleep(100)
            except:
                pass
            await asyncio.sleep(300)

    async def notification(self):
        while True:
            try:
                if not self.req_files:
                    await self.highrise.chat("Şarkı isteği kalmadı. Şarkı istemek için /play yazın.")
            except:
                pass
            await asyncio.sleep(277)

    async def print_messages(self):
        while True:
            try:
                if self.message:
                    nowplaying = self.message[0]
                    # Nothing.mp3 çalarken mesaj gösterme
                    if nowplaying.get('title') == 'Nothing' or nowplaying.get('url') in AUDIO_FILES:
                        self.message.clear()
                        await asyncio.sleep(5)
                        continue

                    fix_nowplaying = nowplaying['title']
                    if nowplaying['user']:
                        await self.highrise.chat(f"🎵 Şu anda çalıyor: {fix_nowplaying}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {nowplaying['audio_length']}\n (@{nowplaying['user']} tarafından istendi)")
                    else:
                        await self.highrise.chat(f"🎵 Şu anda çalıyor: {fix_nowplaying}\n 🎵 ▷ •ı||ıı|ıı|ı||ı|ıı||ı• {nowplaying['audio_length']}")
                    self.message.clear()
            except:
                pass
            await asyncio.sleep(5)

    async def run(self, room_id: str, token: str):
        definitions = [BotDefinition(self, room_id, token)]
        await __main__.main(definitions)

    def get_audio_length(self, audio_path):
        try:
            audio = MP3(audio_path)
            length = audio.info.length
            length = max(length, 0)
            minutes = int(length // 60)
            seconds = int(length % 60)
            return f"{minutes}:{seconds:02d}"
        except Exception:
            # Return default length for invalid MP3 files without logging
            return "0:30"

def get_ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return str(n) + suffix

def connect_to_icecast():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        sock.connect((SERVER_HOST, SERVER_PORT))
        print("Connected to Icecast server.")

        auth = f"source:{STREAM_PASSWORD}"
        headers = (
            f"PUT {MOUNT_POINT} HTTP/1.1\r\n"
            f"Host: {SERVER_HOST}\r\n"
            f"Authorization: Basic {base64.b64encode(auth.encode()).decode()}\r\n"
            f"Content-Type: audio/mpeg\r\n"
            f"User-Agent: Icecast/2.4.0\r\n"
            f"ice-name: ROBINS MUSIC\r\n"
            f"ice-genre: Various\r\n"
            f"ice-url: https://stream.zeno.fm{MOUNT_POINT}\r\n"
            f"ice-public: 1\r\n"
            f"ice-audio-info: bitrate=128000;samplerate=44100;channels=2\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        sock.sendall(headers.encode('utf-8'))

        response = sock.recv(1024).decode('utf-8')
        print(f"Server response: {response}")

        if "HTTP/1.0 200 OK" in response:
            print("Authentication successful.")
        else:
            print("Unexpected server response. Closing connection.")
            sock.close()
            return None
        return sock
    except Exception as e:
        print(f"Connection error: {e}")
        return None


def start_streaming(bot_instance):
    try:
        while True:
            sock = connect_to_icecast()
            if sock:
                try:
                    while True:
                        audio_file = None

                        # Check for requested songs first
                        if bot_instance.req_files:
                            # Verify file still exists
                            if os.path.exists(bot_instance.req_files[0]['url']):
                                audio_file = bot_instance.req_files[0]['url']
                                print(f"Streaming from queue: {bot_instance.req_files[0]['title']}")
                            else:
                                print(f"Requested file missing: {bot_instance.req_files[0]['url']}")
                                bot_instance.req_files.popleft()
                                continue

                        # Check playlist if no requests
                        elif playlist:
                            available_playlist = [item for item in playlist if os.path.exists(item['url'])]
                            if available_playlist:
                                erm = random.choice(available_playlist)
                                audio_file = erm['url']
                                print(f"Streaming from playlist: {erm['title']}")

                        # Default to Nothing.mp3 when queue is empty
                        if audio_file is None:
                            audio_file = random.choice(AUDIO_FILES)
                            # Don't spam console when playing default audio
                            # print(f"Streaming default audio: {audio_file}")

                        success = stream_audio(sock, audio_file, bot_instance)

                        if bot_instance.skip:
                            bot_instance.skip = False
                            continue

                        if not success:
                            sock.close()
                            break

                        # Longer delay when playing default audio to reduce spam
                        if audio_file in AUDIO_FILES:
                            time.sleep(2)
                        else:
                            time.sleep(0.5)

                except Exception as e:
                    print(f"Error during streaming: {e}")
                    if sock:
                        sock.close()
            else:
                print("Failed to connect to Icecast server.")

            time.sleep(5)
    except Exception as e:
        print(f"Error in start_streaming: {e}")

def stream_audio(sock, audio_file, bot_instance):
    try:
        # Only print for non-default audio files to reduce spam
        if audio_file not in AUDIO_FILES:
            print(f"Streaming audio file: {audio_file}")

        # Clear current song info before setting a new one
        bot_instance.now.clear()
        bot_instance.message.clear()

        # Check if file exists first
        if not os.path.exists(audio_file):
            print(f"Audio file not found: {audio_file}")
            return False

        if audio_file in AUDIO_FILES:
            song_title = audio_file.replace(".mp3", "")
            audio_length = bot_instance.get_audio_length(audio_file)
            if audio_length is None:
                audio_length = "0:00"
            bot_instance.now.append({'url': audio_file, 'title': song_title, 'user': None, 'audio_length': audio_length})
            # Nothing.mp3 için mesaj ekleme
            if song_title != "Nothing":
                bot_instance.message.append({'url': audio_file, 'title': song_title, 'user': None, 'audio_length': audio_length})

        elif any(item['url'] == audio_file for item in playlist):
            matching_item = next((item for item in playlist if item['url'] == audio_file), None)
            if matching_item:
                details = {
                    'url': matching_item['url'],
                    'title': matching_item['title'],
                    'user': None,
                    'audio_length': matching_item.get('audio_length', matching_item.get('duration', '0:00'))
                }
                bot_instance.now.append(details)
                bot_instance.message.append(details)

        elif bot_instance.req_files and audio_file == bot_instance.req_files[0]['url']:
            details = {
                'url': bot_instance.req_files[0]['url'],
                'title': bot_instance.req_files[0]['title'],
                'user': bot_instance.req_files[0]['user'],
                'audio_length': bot_instance.req_files[0]['duration']
            }
            bot_instance.now.append(details)
            bot_instance.message.append(details)

        command = [
            './bin/ffmpeg',
            '-re',
            '-i', audio_file,
            '-map', '0:a',
            '-c:a', 'libmp3lame',
            '-ar', '44100',
            '-b:a', bot_instance.bitrate,
            '-f', 'mp3',
            '-content_type', 'audio/mpeg',
            '-buffer_size', '500k',
            '-'
        ]

        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        while True:
            data = process.stdout.read(4096)

            if bot_instance.skip:
                if audio_file not in AUDIO_FILES:
                    print(f"Skipping: {audio_file}")
                process.terminate()

                # Remove from req_files if it was a requested song
                if bot_instance.req_files and bot_instance.req_files[0]['url'] == audio_file:
                    bot_instance.req_files.popleft()

                # Clean up temporary file if it's not a default AUDIO_FILE and not in playlist
                if audio_file not in AUDIO_FILES and not any(item['url'] == audio_file for item in playlist):
                    cleanup_temp_file(bot_instance, audio_file)

                return True # Indicate successful skip

            if not data:
                process.terminate()
                # Only print for non-default audio files to reduce spam
                if audio_file not in AUDIO_FILES:
                    print(f"Finished streaming: {audio_file}")

                # Clean up req_files when song finishes naturally
                if bot_instance.req_files and bot_instance.req_files[0]['url'] == audio_file:
                    bot_instance.req_files.popleft()

                # Clean up temporary file if it's not a default AUDIO_FILE and not in playlist
                if audio_file not in AUDIO_FILES and not any(item['url'] == audio_file for item in playlist):
                    cleanup_temp_file(bot_instance, audio_file)

                # Clear now playing info when song ends
                bot_instance.now.clear()

                return True # Indicate successful stream completion

            try:
                sock.sendall(data)
            except (BrokenPipeError, ConnectionResetError) as e:
                print(f"Connection lost while sending chunk: {e}")
                process.terminate()
                return False # Indicate connection error
            time.sleep(0.05)

    except Exception as e:
        print(f"Streaming error: {e}")
        return False # Indicate streaming error

def cleanup_temp_file(bot_instance, temp_file_path):
    """Remove the temporary file from memory."""
    try:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"Temporary file removed: {temp_file_path}")
    except Exception as e:
        print(f"Error cleaning up temporary file {temp_file_path}: {e}")