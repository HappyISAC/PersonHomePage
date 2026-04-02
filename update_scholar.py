import requests
from scholarly import scholarly
import json
import os

# 1. 设置您的 Google Scholar ID
SCHOLAR_ID = 'OufvGTkAAAAJ' # 请替换为您主页 URL 中 user= 后面的字符串

def update_stats():
    # 搜索作者
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=['basics', 'indices', 'publications'])
    
    # 提取总引用数
    total_citations = author.get('citedby', 0)
    
    # 2. 生成 Shields.io 专用格式 (用于那个蓝色小图标)
    shields_data = {
        "schemaVersion": 1,
        "label": "citations",
        "message": str(total_citations),
        "color": "9cf",
        "style": "flat",
        "labelColor": "f6f6f6"
    }
    
    # 3. 生成详细数据格式 (用于页面文字展示)
    full_data = {
        "citedby": total_citations,
        "publications": {}
    }
    
    # 如果您需要单篇论文引用，可以遍历 author['publications']
    # 这里为了简洁只处理总数
    
    # 写入文件
    os.makedirs('google-scholar-stats', exist_ok=True)
    with open('google-scholar-stats/gs_data_shieldsio.json', 'w') as f:
        json.dump(shields_data, f)
    with open('google-scholar-stats/gs_data.json', 'w') as f:
        json.dump(full_data, f)

    print(f"Successfully updated! Total citations: {total_citations}")

if __name__ == "__main__":
    update_stats()
