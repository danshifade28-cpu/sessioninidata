import asyncio
import os
import re
from urllib.parse import unquote
from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.messages import RequestAppWebViewRequest
from telethon.tl.types import InputBotAppShortName  # 已引入正确的类
from colorama import init, Fore

# 初始化 colorama
init(autoreset=True)

# 请替换为您自己的 API_ID 和 API_HASH
API_ID = 22975977
API_HASH = '432a9f327c7f08ca7f62896e4a9a542d'

SESSIONS_DIR = './sessions'
OUTPUT_FILE = './initData_output.txt'

def parse_message_link(link: str):
    """从消息链接解析 peer (chat) 和 message_id"""
    # 示例: https://t.me/c/123456789/123 或者 https://t.me/public_channel/123
    link = link.strip().rstrip('/')
    parts = link.split('/')
    msg_id = int(parts[-1])
    
    if '/c/' in link:
        # 私密群组/频道
        chat_id = int('-100' + parts[-2])
        return chat_id, msg_id
    else:
        # 公开群组/频道
        chat_id = parts[-2]
        return chat_id, msg_id

async def process_single_account(session_path: str, chat_id, msg_id: int):
    session_name = os.path.splitext(os.path.basename(session_path))[0]
    client = TelegramClient(session_path, API_ID, API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"{Fore.RED}[{session_name}] 账号未授权或已失效")
            return
            
        # 1. 获取消息上下文的 peer 实体
        try:
            peer_entity = await client.get_input_entity(chat_id)
        except Exception as e:
            print(f"{Fore.RED}[{session_name}] 无法获取群组/频道实体，请确认该账号已加入该群组: {e}")
            return
            
        # 2. 获取目标消息
        messages = await client.get_messages(peer_entity, ids=[msg_id])
        if not messages or not messages[0] or not messages[0].reply_markup:
            print(f"{Fore.YELLOW}[{session_name}] 找不到指定消息或消息没有按钮面板")
            return
            
        message = messages[0]
        target_url = None
        
        # 3. 遍历按钮，寻找带有 startapp 的小应用程序链接
        for row in message.reply_markup.rows:
            for btn in row.buttons:
                if hasattr(btn, 'url') and btn.url and 'startapp=' in btn.url:
                    target_url = btn.url
                    break
            if target_url:
                break
                
        if not target_url:
            print(f"{Fore.YELLOW}[{session_name}] 未在消息按钮中找到包含 'startapp=' 的小程序链接")
            return
            
        # 4. 解析目标小程序的三个核心要素: bot_username, app_name, start_param
        match = re.search(r't\.me/([^/]+)/([^?]+)\?startapp=(.*)', target_url)
        if not match:
            print(f"{Fore.YELLOW}[{session_name}] 按钮链接格式无法识别: {target_url}")
            return
            
        bot_username, app_name, start_param = match.groups()
        
        # 5. 发起鉴权请求
        bot_entity = await client.get_input_entity(bot_username)
        
        # 使用 InputBotAppShortName 构建独立小程序标识
        app_input = InputBotAppShortName(bot_id=bot_entity, short_name=app_name)
        
        web_view = await client(RequestAppWebViewRequest(
            peer=peer_entity,          # 使用消息所在的群组上下文，模拟从该群组点击
            app=app_input,             # 目标小程序
            platform='android',
            start_param=start_param    # 填入提取到的邀请参数
        ))
        
        # 6. 提取并保存数据
        auth_url = web_view.url
        tg_web_data = unquote(auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])
        
        with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{tg_web_data}\n")
            
        print(f"{Fore.GREEN}[{session_name}] 成功提取: {bot_username}/{app_name} 并写入 {OUTPUT_FILE}")
        
    except RPCError as e:
        print(f"{Fore.RED}[{session_name}] API 拒绝请求: {e}")
    except Exception as e:
        print(f"{Fore.RED}[{session_name}] 发生未知异常: {e}")
    finally:
        await client.disconnect()

async def main():
    if not os.path.exists(SESSIONS_DIR):
        print(f"找不到 {SESSIONS_DIR} 目录，请先创建并存入 .session 文件。")
        return

    session_files = [f for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    if not session_files:
        print(f"{SESSIONS_DIR} 目录下没有找到任何 .session 文件。")
        return

    print(f"找到 {len(session_files)} 个账号。")
    msg_link = input("请输入 Telegram 消息链接 (例如: https://t.me/channel_name/123): ").strip()
    
    if not msg_link:
        print("链接不能为空")
        return

    try:
        chat_id, msg_id = parse_message_link(msg_link)
    except Exception as e:
        print("解析链接失败，请检查格式是否正确。")
        return

    print(f"\n目标会话: {chat_id}, 目标消息ID: {msg_id}")
    print("开始处理...\n")

    for file_name in session_files:
        session_path = os.path.join(SESSIONS_DIR, file_name)
        await process_single_account(session_path, chat_id, msg_id)
        # 避免被官方限流，每个账号处理完毕后延时 3 秒
        await asyncio.sleep(3)
        
    print(f"\n{Fore.CYAN}全部任务执行完毕！")

if __name__ == "__main__":
    asyncio.run(main())