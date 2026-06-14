from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

class DocumentType(Enum):
    SUPPLIER_BILL = "supplier_bill"
    RECEIVING_LIST = "receiving_list"

class OperatorRole(Enum):
    REVIEWER = "reviewer"
    APPROVER = "approver"
    ADMIN = "admin"

    @classmethod
    def is_valid(cls, role: str) -> bool:
        return role.lower() in [r.value for r in cls]

    @classmethod
    def from_string(cls, role: str) -> 'OperatorRole':
        role_lower = role.lower()
        for r in cls:
            if r.value == role_lower:
                return r
        raise ValueError(f"无效的角色: {role}，有效角色: {[r.value for r in cls]}")

    @classmethod
    def can_approve(cls, role: str) -> bool:
        return role.lower() in [cls.APPROVER.value, cls.ADMIN.value]

    @classmethod
    def can_reject(cls, role: str) -> bool:
        return role.lower() in [cls.APPROVER.value, cls.ADMIN.value]

    @classmethod
    def can_rollback(cls, role: str) -> bool:
        return role.lower() == cls.ADMIN.value

class AppealStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"

class BatchStatus(Enum):
    OPEN = "open"
    LOCKED = "locked"
    COMPLETED = "completed"

@dataclass
class SupplierBillItem:
    bill_no: str
    item_code: str
    item_name: str
    quantity: float
    unit_price: float
    amount: float
    bill_date: str
    supplier_code: str
    supplier_name: str

@dataclass
class ReceivingListItem:
    receive_no: str
    item_code: str
    item_name: str
    quantity: float
    unit_price: float
    amount: float
    receive_date: str
    supplier_code: str
    supplier_name: str
    purchase_order_no: str

@dataclass
class DiffItem:
    bill_no: str
    receive_no: str
    item_code: str
    item_name: str
    bill_quantity: float
    receive_quantity: float
    quantity_diff: float
    bill_amount: float
    receive_amount: float
    amount_diff: float
    supplier_code: str
    supplier_name: str
    id: Optional[int] = None
    batch_id: Optional[int] = None
    status: AppealStatus = AppealStatus.PENDING
    appeal_note: str = ""
    operator: str = ""
    operator_role: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Batch:
    batch_no: str
    id: Optional[int] = None
    status: BatchStatus = BatchStatus.OPEN
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    lock_time: Optional[datetime] = None

@dataclass
class AuditLog:
    batch_id: int
    batch_no: str
    operation: str
    operator: str
    id: Optional[int] = None
    operator_role: str = ""
    target_item_id: Optional[int] = None
    note: str = ""
    created_at: Optional[datetime] = None

@dataclass
class Config:
    key: str
    value: str
    id: Optional[int] = None
    description: str = ""
    updated_at: Optional[datetime] = None

@dataclass
class ReconciliationRule:
    quantity_tolerance: float = 0.0
    amount_tolerance: float = 0.0
    allow_partial_appeal: bool = True

@dataclass
class ValidationError:
    row: int
    field: str
    value: str
    error_type: str
    message: str

@dataclass
class ValidationResult:
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    valid_rows: List[Dict[str, Any]] = field(default_factory=list)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def get_error_summary(self) -> str:
        if not self.errors:
            return ""
        lines = [f"发现 {len(self.errors)} 个验证错误:"]
        for err in self.errors:
            lines.append(f"  行 {err.row}: [{err.error_type}] {err.field}={err.value} - {err.message}")
        return "\n".join(lines)