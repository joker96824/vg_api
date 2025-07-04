import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.database import get_session
from src.core.services.card_import import CardImportService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/import/json", response_model=Dict[str, int])
async def import_cards_from_json(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session)
):
    """
    从 JSON 文件导入卡牌数据
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="只支持 JSON 文件")

    try:
        # 保存上传的文件
        file_path = f"temp/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 导入数据
        import_service = CardImportService(session)
        results = await import_service.import_from_json_file(file_path)

        return results

    except Exception as e:
        logger.error(f"导入卡牌数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/batch", response_model=Dict[str, int])
async def import_cards_batch(
    cards_data: List[Dict],
    session: AsyncSession = Depends(get_session)
):
    """
    批量导入卡牌数据
    """
    try:
        import_service = CardImportService(session)
        results = await import_service.import_cards_batch(cards_data)
        return results

    except Exception as e:
        logger.error(f"批量导入卡牌数据失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 