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
    scheme_name: Optional[str] = None
    scheme_snapshot: Optional[Dict[str, Any]] = None

    def get_scheme_snapshot_summary(self) -> str:
        if not self.scheme_snapshot:
            return "(无)"
        snap = self.scheme_snapshot
        parts = [f"方案:{snap.get('name', '未知')}"]
        parts.append(f"数量容差±{snap.get('quantity_tolerance', 0)}")
        parts.append(f"金额容差±{snap.get('amount_tolerance', 0)}")
        if snap.get('date_offset_days', 0) != 0:
            parts.append(f"日期偏移{snap.get('date_offset_days')}天")
        if snap.get('required_fields'):
            parts.append(f"必填:{','.join(snap['required_fields'])}")
        if snap.get('ignored_fields'):
            parts.append(f"忽略:{','.join(snap['ignored_fields'])}")
        return "; ".join(parts)

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
class RuleScheme:
    name: str
    business_line: str = ""
    description: str = ""
    quantity_tolerance: float = 0.0
    amount_tolerance: float = 0.0
    date_offset_days: int = 0
    required_fields: List[str] = field(default_factory=list)
    ignored_fields: List[str] = field(default_factory=list)
    is_active: bool = False
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'business_line': self.business_line,
            'description': self.description,
            'quantity_tolerance': self.quantity_tolerance,
            'amount_tolerance': self.amount_tolerance,
            'date_offset_days': self.date_offset_days,
            'required_fields': self.required_fields,
            'ignored_fields': self.ignored_fields,
            'is_active': self.is_active,
        }

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'business_line': self.business_line,
            'description': self.description,
            'quantity_tolerance': self.quantity_tolerance,
            'amount_tolerance': self.amount_tolerance,
            'date_offset_days': self.date_offset_days,
            'required_fields': list(self.required_fields),
            'ignored_fields': list(self.ignored_fields),
        }

    def get_snapshot_summary(self) -> str:
        parts = [f"数量容差±{self.quantity_tolerance}", f"金额容差±{self.amount_tolerance}"]
        if self.date_offset_days != 0:
            parts.append(f"日期偏移{self.date_offset_days}天")
        if self.required_fields:
            parts.append(f"必填:{','.join(self.required_fields)}")
        if self.ignored_fields:
            parts.append(f"忽略:{','.join(self.ignored_fields)}")
        return "; ".join(parts)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleScheme':
        return cls(
            name=data['name'],
            business_line=data.get('business_line', ''),
            description=data.get('description', ''),
            quantity_tolerance=float(data.get('quantity_tolerance', 0.0)),
            amount_tolerance=float(data.get('amount_tolerance', 0.0)),
            date_offset_days=int(data.get('date_offset_days', 0)),
            required_fields=data.get('required_fields', []),
            ignored_fields=data.get('ignored_fields', []),
            is_active=data.get('is_active', False),
        )

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