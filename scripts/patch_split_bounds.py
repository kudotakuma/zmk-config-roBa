"""Reject non-peripheral disconnects and invalid battery event indices."""
from pathlib import Path
import hashlib,sys
HASHES = {'bluetooth/central.c': 'c82daf9d0b9423264375edb224123857f6c8f7d210eda065b6330add77ac651a', 'central.c': 'ec39904d28420f5cfd72a6814d97d137e4ba03ca6d17be76cda91e9c14e61f28'}

def patch_bt(s):
    if 'roBa: ignore disconnects outside the split peripherals' in s:return s
    assert hashlib.sha256(s.encode()).hexdigest()==HASHES['bluetooth/central.c']
    start=s.index('static void split_central_disconnected(');end=s.index('static void split_central_security_changed(',start)
    part=s[start:end]
    anchor='#if IS_ENABLED(CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING)'
    assert part.count(anchor)==1
    part=part.replace(anchor,'''/* roBa: ignore disconnects outside the split peripherals. The host link
     * is also delivered to this callback and has no peripheral slot. */
    int slot_idx = peripheral_slot_index_for_conn(conn);
    if (slot_idx < 0) {
        return;
    }

'''+anchor,1)
    part=part.replace('.source = peripheral_slot_index_for_conn(conn),','.source = slot_idx,',1)
    return s[:start]+part+s[end:]

def patch_handler(s):
    if 'roBa: validate battery source before indexing' in s:return s
    assert hashlib.sha256(s.encode()).hexdigest()==HASHES['central.c']
    anchor='    case ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_BATTERY_EVENT: {'
    assert s.count(anchor)==1
    return s.replace(anchor,anchor+'''
        /* roBa: validate battery source before indexing. */
        if (source >= ARRAY_SIZE(peripheral_battery_levels)) {
            return -EINVAL;
        }''',1)

if __name__=='__main__':
    root=Path(sys.argv[1])
    for rel,fn in [('bluetooth/central.c',patch_bt),('central.c',patch_handler)]:
        p=root/rel;p.write_text(fn(p.read_text()));print('roBa split bounds patch:',rel,hashlib.sha256(p.read_bytes()).hexdigest())
