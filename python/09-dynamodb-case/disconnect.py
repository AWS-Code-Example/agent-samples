"""
WebSocket默认路由处理 - $default路由
处理WebSocket消息，包括查询请求和响应
"""
import sys
import os
import json
import boto3

# 添加shared目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))

from bedrock_client import BedrockClient
from db_client import DBClient
from context_manager import ContextManager
from query_executor import QueryExecutor

# 初始化客户端
bedrock = BedrockClient()
db = DBClient()
context_mgr = ContextManager()
executor = QueryExecutor()


def lambda_handler(event, context):
    """
    处理WebSocket消息（查询请求）

    Args:
        event: API Gateway事件
        context: Lambda上下文

    Returns:
        dict: 响应对象
    """
    try:
        # 获取连接信息
        connection_id = event.get('requestContext', {}).get('connectionId')
        domain_name = event.get('requestContext', {}).get('domainName')
        stage = event.get('requestContext', {}).get('stage')

        if not connection_id:
            print("Error: No connectionId in event")
            return {'statusCode': 400}

        # 解析请求体
        body = event.get('body', '')
        try:
            request_data = json.loads(body)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in body: {body}")
            return {'statusCode': 400}

        # 提取请求参数
        action = request_data.get('action')
        question = request_data.get('question')
        question_id = request_data.get('question_id')

        print(f"Received request - Action: {action}, Question: {question}, QuestionId: {question_id}")

        # 验证必需参数
        if not question:
            _send_response(connection_id, domain_name, stage, {'error': 'Missing question parameter'})
            return {'statusCode': 400}

        # 获取该连接的上下文
        session_context = context_mgr.get_context(connection_id)
        last_context = session_context['history'][-1] if session_context.get('history') else None

        print(f"Last context: {last_context}")

        # 调用Bedrock解析查询意图
        print("Calling Bedrock to parse query...")
        parsed_query = bedrock.parse_query(question, last_context)
        print(f"Parsed query: {json.dumps(parsed_query, ensure_ascii=False)}")

        # 根据筛选条件获取数据
        print("Fetching data from DynamoDB...")
        records = _get_records_for_query(parsed_query)
        print(f"Retrieved {len(records)} records")

        # 执行查询并获取结果
        print("Executing query...")
        answer = executor.execute(parsed_query, records)
        print(f"Query result: {answer}")

        # 构造响应
        response = {'answer': answer}
        if question_id:
            response['question_id'] = question_id

        # 发送WebSocket响应
        _send_response(connection_id, domain_name, stage, response)

        # 更新上下文（保存对话历史）
        context_mgr.add_to_history(connection_id, question, answer, parsed_query)

        print("Query processed successfully")

        return {'statusCode': 200}

    except Exception as e:
        print(f"Error in default handler: {e}")
        import traceback
        traceback.print_exc()

        # 尝试发送错误响应
        connection_id = event.get('requestContext', {}).get('connectionId')
        domain_name = event.get('requestContext', {}).get('domainName')
        stage = event.get('requestContext', {}).get('stage')

        if connection_id:
            _send_response(connection_id, domain_name, stage, {'error': str(e)})

        return {'statusCode': 500}


def _get_records_for_query(parsed_query):
    """
    根据解析后的查询参数获取记录

    Args:
        parsed_query: 解析后的查询参数

    Returns:
        list: 记录列表
    """
    filters = parsed_query.get('filters', {})

    # 如果有明确的筛选条件，使用对应的方法
    if filters.get('service_date'):
        return db.query_by_service_date(filters['service_date'])
    elif filters.get('bill_date'):
        return db.query_by_bill_date(filters['bill_date'])
    elif filters.get('service_name'):
        return db.query_by_service_name(filters['service_name'])
    else:
        # 没有筛选条件，返回所有记录
        return db.get_all_records()


def _send_response(connection_id, domain_name, stage, data):
    """
    通过WebSocket发送响应给客户端

    Args:
        connection_id: WebSocket连接ID
        domain_name: API Gateway域名
        stage: API Gateway阶段
        data: 要发送的数据（会被转换为JSON）
    """
    if not connection_id or not domain_name:
        print("Missing connection_id or domain_name, cannot send response")
        return

    try:
        # 构造API Gateway Management API的端点
        endpoint_url = f"https://{domain_name}/{stage}"

        # 创建API Gateway客户端
        apigateway_client = boto3.client(
            'apigatewaymanagementapi',
            endpoint_url=endpoint_url,
            region_name='us-east-1'
        )

        # 发送消息
        response = apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data, ensure_ascii=False)
        )

        print(f"Response sent successfully: {data}")

    except apigateway_client.exceptions.GoneException:
        print(f"Connection {connection_id} is no longer active")
    except Exception as e:
        print(f"Error sending response: {e}")
