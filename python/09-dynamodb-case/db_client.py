"""
Bedrock客户端 - 调用amazon.nova-lite-v1:0模型解析自然语言查询
"""
import boto3
import json
import re


class BedrockClient:
    """Amazon Bedrock AI客户端"""

    def __init__(self, model_id=None, region=None):
        """
        初始化Bedrock客户端

        Args:
            model_id: 模型ID，默认amazon.nova-lite-v1:0
            region: 区域，默认us-east-1
        """
        self.model_id = model_id or 'amazon.nova-lite-v1:0'
        self.region = region or 'us-east-1'
        self.client = boto3.client('bedrock-runtime', region_name=self.region)

    def parse_query(self, question, last_context=None):
        """
        使用Bedrock模型解析用户问题，返回结构化查询参数

        Args:
            question: 用户问题（中文自然语言）
            last_context: 上一次对话的上下文信息

        Returns:
            dict: 解析后的查询参数，包含:
                - query_type: 查询类型 (count/sum/avg/max/min/top_n)
                - filters: 筛选条件
                - sort_field: 排序字段
                - sort_order: 排序方向 (desc/asc)
                - limit: 限制数量
                - requires_context: 是否需要上下文
                - resolved_entity: 解析出的实体类型
        """
        prompt = self._build_prompt(question, last_context)

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps({
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0
                })
            )

            response_body = json.loads(response['body'].read())
            content = response_body.get('content', [])

            if content and len(content) > 0:
                result_text = content[0].get('text', '')
                # 尝试解析JSON
                return self._parse_result(result_text)

            # 默认返回基本查询
            return self._get_default_result()

        except Exception as e:
            print(f"Error calling Bedrock: {e}")
            return self._get_default_result()

    def _build_prompt(self, question, last_context):
        """
        构建发送给Bedrock的提示词

        Args:
            question: 用户问题
            last_context: 上一次对话的上下文

        Returns:
            str: 格式化的提示词
        """
        last_context_str = json.dumps(last_context, ensure_ascii=False) if last_context else "无"

        prompt = f"""你是一个云账单数据查询助手。根据用户问题，返回JSON格式的查询参数。

数据表结构：
- service_date: 格式 "服务名#日期"，例如 "Amazon Elastic Compute Cloud#2025-11-26"
- service_name: AWS服务名，例如 "Amazon Elastic Compute Cloud", "Amazon Simple Storage Service"
- bill_date: 账单日期，格式 "YYYY-MM-DD"
- total_cost: 总成本（数字，单位美元）
- record_count: 记录数量

查询类型说明：
1. count: 统计数量（通常用于统计服务数量或记录数）
2. sum: 求和总成本
3. avg: 计算平均成本
4. max: 获取最高成本
5. min: 获取最低成本
6. top_n: 按消耗排序取第N项（需要指定limit和resolved_entity）

上下文（上一次查询）：
{last_context_str}

用户问题：{question}

请返回JSON格式：
{{
  "query_type": "count|sum|avg|max|min|top_n",
  "filters": {{
    "service_name": "服务名或null",
    "bill_date": "日期或null",
    "service_date": "服务日期或null"
  }},
  "sort_field": "total_cost或null",
  "sort_order": "desc或asc",
  "limit": 数字或null（仅top_n需要）,
  "requires_context": true或false,
  "resolved_entity": "service_name或bill_date或null（仅top_n需要，指定要返回的是服务名还是日期）"
}}
只返回JSON，不要其他内容。"""
        return prompt

    def _parse_result(self, result_text):
        """
        解析Bedrock返回的结果

        Args:
            result_text: Bedrock返回的文本

        Returns:
            dict: 解析后的查询参数
        """
        try:
            # 尝试提取JSON（可能包含在markdown代码块中）
            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                return self._validate_and_normalize(result)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}, raw: {result_text}")

        # 解析失败，返回默认结果
        return self._get_default_result()

    def _validate_and_normalize(self, result):
        """
        验证和规范化查询参数

        Args:
            result: 原始查询参数

        Returns:
            dict: 规范化后的查询参数
        """
        # 确保必要的字段存在
        if 'filters' not in result:
            result['filters'] = {}

        if 'query_type' not in result:
            result['query_type'] = 'sum'

        # 规范化filters中的null值
        filters = result['filters']
        for key in ['service_name', 'bill_date', 'service_date']:
            if filters.get(key) == 'null' or filters.get(key) is None:
                filters[key] = None

        # 确保数值类型
        if 'limit' in result and result['limit'] is not None:
            try:
                result['limit'] = int(result['limit'])
            except (ValueError, TypeError):
                result['limit'] = 1

        return result

    def _get_default_result(self):
        """
        获取默认的查询参数（当解析失败时使用）

        Returns:
            dict: 默认查询参数
        """
        return {
            'query_type': 'sum',
            'filters': {
                'service_name': None,
                'bill_date': None,
                'service_date': None
            },
            'sort_field': 'total_cost',
            'sort_order': 'desc',
            'limit': None,
            'requires_context': False,
            'resolved_entity': None
        }
