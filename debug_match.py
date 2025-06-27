#!/usr/bin/env python3
"""
调试匹配功能的脚本
"""
import json
import asyncio
from datetime import datetime
from src.core.utils.redis import get_key, set_key, delete_key

async def debug_match_data():
    """调试匹配相关的Redis数据"""
    print("=== 调试匹配数据 ===")
    
    # 检查匹配队列
    match_queue_key = "match_queue"
    queue_data = get_key(match_queue_key)
    print(f"匹配队列数据: {queue_data}")
    
    if queue_data:
        try:
            queue_info = json.loads(queue_data)
            print(f"解析后的队列信息: {json.dumps(queue_info, indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError as e:
            print(f"解析队列数据失败: {e}")
    
    # 检查待确认的匹配
    pending_matches_key = "pending_matches"
    pending_data = get_key(pending_matches_key)
    print(f"\n待确认匹配数据: {pending_data}")
    
    if pending_data:
        try:
            pending_matches = json.loads(pending_data)
            print(f"解析后的待确认匹配: {json.dumps(pending_matches, indent=2, ensure_ascii=False)}")
            
            # 检查每个匹配的expire_time字段
            for match_id, match_info in pending_matches.items():
                print(f"\n匹配ID: {match_id}")
                print(f"匹配信息: {json.dumps(match_info, indent=2, ensure_ascii=False)}")
                
                if "expire_time" in match_info:
                    try:
                        expire_time = datetime.fromisoformat(match_info["expire_time"])
                        current_time = datetime.utcnow()
                        print(f"过期时间: {expire_time}")
                        print(f"当前时间: {current_time}")
                        print(f"是否已过期: {current_time > expire_time}")
                    except (ValueError, TypeError) as e:
                        print(f"解析expire_time失败: {e}")
                else:
                    print("缺少expire_time字段")
        except json.JSONDecodeError as e:
            print(f"解析待确认匹配数据失败: {e}")
    
    print("\n=== 调试完成 ===")

if __name__ == "__main__":
    asyncio.run(debug_match_data()) 