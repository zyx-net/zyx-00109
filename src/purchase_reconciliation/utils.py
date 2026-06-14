import csv
from typing import List

from .models import SupplierBillItem, ReceivingListItem

def read_supplier_bill(file_path: str) -> List[SupplierBillItem]:
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(SupplierBillItem(
                bill_no=row['bill_no'],
                item_code=row['item_code'],
                item_name=row['item_name'],
                quantity=float(row['quantity']),
                unit_price=float(row['unit_price']),
                amount=float(row['amount']),
                bill_date=row['bill_date'],
                supplier_code=row['supplier_code'],
                supplier_name=row['supplier_name']
            ))
    return items

def read_receiving_list(file_path: str) -> List[ReceivingListItem]:
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(ReceivingListItem(
                receive_no=row['receive_no'],
                item_code=row['item_code'],
                item_name=row['item_name'],
                quantity=float(row['quantity']),
                unit_price=float(row['unit_price']),
                amount=float(row['amount']),
                receive_date=row['receive_date'],
                supplier_code=row['supplier_code'],
                supplier_name=row['supplier_name'],
                purchase_order_no=row['purchase_order_no']
            ))
    return items

def generate_batch_no() -> str:
    from datetime import datetime
    now = datetime.now()
    return f"BATCH_{now.strftime('%Y%m%d_%H%M%S')}"

def validate_csv_structure(file_path: str, required_fields: List[str]) -> bool:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            missing_fields = [f for f in required_fields if f not in fieldnames]
            if missing_fields:
                print(f"错误: 文件缺少必需字段: {', '.join(missing_fields)}")
                return False
            return True
    except Exception as e:
        print(f"错误: 无法读取文件 {file_path}: {str(e)}")
        return False