"""
上下文管理器 - 使用DynamoDB持久化存储WebSocket会话上下文
"""
import boto3
import json
from datetime import datetime
import os


class ContextManager:
    """WebSocket会话上下文管理器"""

    def __init__(self, table_name=None):
        """
        初始化上下文管理器

        Args:
            table_name: DynamoDB表名，默认从环境变量读取或使用WebSocket_Context
        """
        self.dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table_name = table_name or os.environ.get('CONTEXT_TABLE_NAME', 'WebSocket_Context')
        self.table = self.dynamodb.Table(self.table_name)
        self.max_history = 5  # 最多保留5条历史记录

    def save_context(self, connection_id, context):
        """
        保存上下文

        Args:
            connection_id: WebSocket连接ID
            context: 上下文字典
        """
        try:
            self.table.put_item(
                Item={
                    'connection_id': connection_id,
                    'session_data': json.dumps(context, ensure_ascii=False),
                    'updated_at': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            print(f"Error saving context for {connection_id}: {e}")
            raise

    def get_context(self, connection_id):
        """
        获取上下文

        Args:
            connection_id: WebSocket连接ID

        Returns:
            dict: 上下文字典，包含history列表
        """
        try:
            response = self.table.get_item(Key={'connection_id': connection_id})
            if 'Item' in response:
                return json.loads(response['Item']['session_data'])
            return {'history': []}
        except Exception as e:
            print(f"Error getting context for {connection_id}: {e}")
            return {'history': []}

    def clear_context(self, connection_id):
        """
        清除上下文

        Args:
            connection_id: WebSocket连接ID
        """
        try:
            self.table.delete_item(Key={'connection_id': connection_id})
        except Exception as e:
            print(f"Error clearing context for {connection_id}: {e}")

    def add_to_history(self, connection_id, question, answer, parsed_query=None):
        """
        添加对话历史

        Args:
            connection_id: WebSocket连接ID
            question: 用户问题
            answer: 系统答案
            parsed_query: 解析后的查询参数（用于上下文理解）
        """
        context = self.get_context(connection_id)

        # 添加新的对话记录
        history_entry = {
            'question': question,
            'answer': answer
        }

        # 如果有解析后的查询信息，也保存
        if parsed_query:
            history_entry['parsed_query'] = parsed_query

        context['history'].append(history_entry)

        # 只保留最近的N条历史
        if len(context['history']) > self.max_history:
            context['history'] = context['history'][-self.max_history:]

        self.save_context(connection_id, context)

    def get_last_context(self, connection_id):
        """
        获取上一次对话的上下文（用于代词解析）

        Args:
            connection_id: WebSocket连接ID

        Returns:
            dict or None: 上一次的对话记录，如果不存在则返回None
        """
        context = self.get_context(connection_id)
        if context.get('history'):
            return context['history'][-1]
        return None
