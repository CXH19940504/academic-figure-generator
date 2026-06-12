"""Simple test script for outline generation endpoints (no pytest dependency)."""

import asyncio
import sys
sys.path.insert(0, "/Users/chenxuhan/Documents/workspace/academic-figure-generator/backend")

from app.main import app
from httpx import AsyncClient, ASGITransport


async def test_outline_generate():
    """Test /outline/generate endpoint."""
    print("\n=== Test 1: /outline/generate ===")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outline/generate",
            json={
                "project_id": None,
                "title": "基于深度学习的图像识别技术研究",
                "paper_type": 1,
                "subject_code": "08",
                "subject_name": "计算机科学与技术",
                "degree": "本科",
                "word_count": 15000,
                "template_id": None,
            },
        )
        
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Message: {data.get('message')}")
        print(f"Document ID: {data.get('document_id')}")
        print(f"Duration: {data.get('duration_ms')} ms")
        
        assert response.status_code == 200
        assert data["success"] == True
        print("✅ Test passed")


async def test_outline_generate_direct():
    """Test /outline/generate-direct endpoint."""
    print("\n=== Test 2: /outline/generate-direct ===")
    
    custom_prompt = """
    你是一位学术论文写作专家，请根据以下要求生成论文大纲：
    1. 大纲需要包含摘要、引言、正文和结论
    2. 正文部分需要至少3个章节
    3. 每个章节需要清晰的标题和层级
    """
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/outline/generate-direct",
            json={
                "document_id": None,
                "title": "基于区块链的数据安全技术研究",
                "paper_type": 1,
                "subject_code": "08",
                "subject_name": "信息安全",
                "degree": "本科",
                "word_count": 20000,
                "outline_prompt": custom_prompt,
            },
        )
        
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Success: {data.get('success')}")
        print(f"Message: {data.get('message')}")
        print(f"Document ID: {data.get('document_id')}")
        print(f"Duration: {data.get('duration_ms')} ms")
        
        assert response.status_code == 200
        assert data["success"] == True
        print("✅ Test passed")


async def test_outline_with_project():
    """Test outline generation with project association."""
    print("\n=== Test 3: /outline/generate with project ===")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First create a project
        project_response = await client.post(
            "/api/v1/projects",
            json={
                "name": "Test Project for Outline",
                "paper_field": "计算机科学",
            },
        )
        
        if project_response.status_code == 200:
            project_id = project_response.json()["id"]
            print(f"Created project: {project_id}")
            
            # Generate outline with project
            response = await client.post(
                "/outline/generate",
                json={
                    "project_id": project_id,
                    "title": "人工智能在医疗诊断中的应用研究",
                    "paper_type": 2,
                    "subject_code": "10",
                    "subject_name": "临床医学",
                    "degree": "硕士",
                    "word_count": 30000,
                    "template_id": None,
                },
            )
            
            print(f"Status: {response.status_code}")
            data = response.json()
            print(f"Success: {data.get('success')}")
            print(f"Document ID: {data.get('document_id')}")
            
            assert response.status_code == 200
            assert data["success"] == True
            print("✅ Test passed")
        else:
            print("⚠️ Could not create project, skipping test")


async def main():
    """Run all tests."""
    print("=" * 50)
    print("Outline API Tests")
    print("=" * 50)
    
    try:
        await test_outline_generate()
    except Exception as e:
        print(f"❌ Test 1 failed: {e}")
    
    try:
        await test_outline_generate_direct()
    except Exception as e:
        print(f"❌ Test 2 failed: {e}")
    
    try:
        await test_outline_with_project()
    except Exception as e:
        print(f"❌ Test 3 failed: {e}")
    
    print("\n" + "=" * 50)
    print("Tests completed")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())