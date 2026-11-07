"""Conservative three-way DID character merge (protocol 1 optional extension).

The baseline must be the *previous synchronized character*, not the latest
Android snapshot. Never silently choose a winner for concurrent note/item text.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from uuid import uuid5, NAMESPACE_URL
import json

MISSING = object()
HP_AT = {('HP', 'current_HP'), ('Adversity', 'current_AT')}
COLLECTIONS = {('notes','list_of_notes'), ('inventory','list_of_items')}

@dataclass
class MergeResult:
    merged: dict | None
    conflicting_resources: tuple[str, ...] = ()


def _eq(a, b):
    return a == b if a is not MISSING and b is not MISSING else a is b


def _j(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _variant_id(kind, item_id, base, phone):
    return str(uuid5(NAMESPACE_URL, f'DID-sync-{kind}:{item_id}:{_j(base) if base is not MISSING else "missing"}:{_j(phone)}'))


def _list_by_id(items):
    if not isinstance(items, list):
        return None
    out={}
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'].strip() or item['id'] in out:
            return None
        out[item['id']]=item
    return out


def _changed(base, x):
    return not _eq(base, x)


def merge_characters(base: dict, pc: dict, phone: dict, *, hp_at_choice: str | None = None) -> MergeResult:
    """Merge without discarding notes or inventory. Missing/invalid base raises.

    hp_at_choice must be 'pc', 'phone', or None. A choice is requested only for
    conflicting concurrent changes to HP.current_HP or Adversity.current_AT.
    """
    if not all(isinstance(x,dict) for x in (base,pc,phone)):
        raise ValueError('Cannot merge without three complete character snapshots')
    ids={str(d.get('id','')).strip() for d in (base,pc,phone)}
    if len(ids)!=1 or not next(iter(ids)):
        raise ValueError('Different character IDs; refusing to merge')
    if hp_at_choice not in (None,'pc','phone'):
        raise ValueError('Unsupported HP/AT resolution')
    pending=[]

    def node(b,p,h,path):
        if path[-1:] == ('quantity',) and len(path)>3 and path[0]=='inventory':
            # Both sides changed the same count: keep both relative deltas.
            # This is different from simultaneous edits to the item's text.
            if all(type(q)==int and q>=0 for q in (b,p,h)):
                if p != b and h != b:
                    return max(0, b + (p-b) + (h-b))
        if isinstance(p,dict) and isinstance(h,dict) and path not in HP_AT:
            bdict=b if isinstance(b,dict) else {}
            result={}
            for k in dict.fromkeys([*bdict,*p,*h]):
                v=node(bdict.get(k,MISSING),p.get(k,MISSING),h.get(k,MISSING),path+(k,))
                if v is not MISSING:result[k]=v
            return result
        if path in COLLECTIONS and isinstance(p,list) and isinstance(h,list):
            return collection(b,p,h,path)
        if _eq(p,h):return deepcopy(p) if p is not MISSING else MISSING
        if _eq(p,b):return deepcopy(h) if h is not MISSING else MISSING
        if _eq(h,b):return deepcopy(p) if p is not MISSING else MISSING
        if path in HP_AT:
            if hp_at_choice is None:
                pending.append('HP' if path[0]=='HP' else 'AT')
                return deepcopy(p)
            return deepcopy(p if hp_at_choice=='pc' else h)
        # Same scalar/list field edited concurrently: retain PC's active field;
        # do not overwrite it. The phone alternative is recorded by the caller
        # as a non-destructive copy in _sync_alternatives.
        if not _eq(p,h):
            alternatives.append({'path':list(path),'pc':None if p is MISSING else deepcopy(p),
                                 'phone':None if h is MISSING else deepcopy(h)})
        return deepcopy(p) if p is not MISSING else deepcopy(h)

    def collection(b,p,h,path):
        bd=_list_by_id(b) if isinstance(b,list) else {}
        pd=_list_by_id(p); hd=_list_by_id(h)
        if bd is None or pd is None or hd is None:
            # Invalid or legacy id-less list: preserve both arrays as copies
            # (deduplicate exact same values) rather than risk data loss.
            result=deepcopy(p)
            for item in h:
                if item not in result:result.append(deepcopy(item))
            return result
        result=[]
        for item_id in dict.fromkeys([*bd,*pd,*hd]):
            bv=bd.get(item_id,MISSING); pv=pd.get(item_id,MISSING); hv=hd.get(item_id,MISSING)
            if pv is MISSING and hv is MISSING:continue
            if _eq(pv,hv):
                # Descend into an identically edited inventory item to count
                # *both* offline quantity deltas rather than only one device.
                value = node(bv,pv,hv,path+('id='+item_id,)) if (
                    path[0]=='inventory' and bv is not MISSING and pv is not MISSING
                ) else deepcopy(pv)
            elif _eq(pv,bv): value=deepcopy(hv) if hv is not MISSING else MISSING
            elif _eq(hv,bv): value=deepcopy(pv) if pv is not MISSING else MISSING
            elif pv is MISSING or hv is MISSING:
                # Delete-vs-edit: prefer preserving the still-existing copy.
                value=deepcopy(pv if pv is not MISSING else hv)
            else:
                # Edit-vs-edit on one record: merge independent fields, but
                # duplicate irreconcilable text changes instead of overwriting.
                sub_alternatives_len=len(alternatives)
                value=node(bv,pv,hv,path+('id='+item_id,))
                if len(alternatives)>sub_alternatives_len:
                    del alternatives[sub_alternatives_len:]
                    # Preserve both whole versions in distinct records. This
                    # also makes the result stable across retried syncs.
                    value=deepcopy(pv)
                    duplicate=deepcopy(hv)
                    duplicate['id']=_variant_id(path[0],item_id,bv,hv)
                    title='title' if path[0]=='notes' else 'name'
                    duplicate[title]=(str(duplicate.get(title,'')).strip()+' (Phone edit)').strip()
                    if not any(x.get('id')==duplicate['id'] for x in result):
                        # Add only if not already present in PC list; see below.
                        if duplicate['id'] not in pd and duplicate['id'] not in hd:
                            result.append(duplicate)
            if value is not MISSING:
                result.append(value)
        return result

    alternatives=[]
    merged=node(base,pc,phone,())
    if pending:
        return MergeResult(None,tuple(dict.fromkeys(pending)))
    # Unknown scalar conflicts are preserved in a persistent (non-transport)
    # field. Future client builds may expose their review history.
    if alternatives:
        seen={_j(a) for a in merged.get('sync_alternatives',[]) if isinstance(a,dict)} if isinstance(merged.get('sync_alternatives'),list) else set()
        log=merged.setdefault('sync_alternatives',[])
        for a in alternatives:
            if _j(a) not in seen:
                log.append(a);seen.add(_j(a))
    return MergeResult(merged)
