"""
WebSocket连接处理 - $connect路由
处理WebSocket客户端连接建立请求
"""
import sys
import os

# 添加shared目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from context_manager import ContextManager

# 初始化上下文管理器
context_mgr = ContextManager()


def lambda_handler(event, context):
    """
    处理WebSocket连接请求

    Args:
        event: API Gateway事件
        context: Lambda上下文

    Returns:
        dict: 响应对象
    """
    try:
        connection_id = event.get('requestContext', {}).get('connectionId')

        if not connection_id:
            print("Error: No connectionId in event")
            return {
                'statusCode': 400,
                'body': 'Missing connectionId'
            }

        # 初始化该连接的上下文
        session_context = {
            'connected_at': context.get('requestTime') or '',
            'history': []
        }

        context_mgr.save_context(connection_id, session_context)

        print(f"Connection established: {connection_id}")

        return {
            'statusCode': 200,
            'body': 'Connected'
        }

    except Exception as e:
        print(f"Error in connect handler: {e}")
        return {
            'statusCode': 500,
            'body': f'Connection failed: {str(e)}'
        }
