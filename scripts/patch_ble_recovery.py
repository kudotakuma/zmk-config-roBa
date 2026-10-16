"""Apply the roBa recovery patch only to the exact reviewed upstream source."""
from pathlib import Path
import hashlib
import sys

BASE_SHA = 'ab936cdb01c2c9ddd3c90ac1c231fb18b791f92e2f5ab8e934b8d8bbd23291d0'
MARKER = 'roBa: reconcile advertising every five seconds'

def patch(source):
    if MARKER in source:
        return source
    assert hashlib.sha256(source.encode()).hexdigest() == BASE_SHA, 'Unexpected upstream ble.c'
    start = source.index('#define CHECKED_OPEN_ADV()')
    end = source.index('\nint update_advertising(void)', start)
    macro = source[start:end]
    assert macro.count('if (err)') == 1
    source = source[:start] + macro.replace('if (err)', 'if (err && err != -EALREADY)') + source[end:]
    source = source.replace('    case ZMK_ADV_CONN + CURR_ADV(ZMK_ADV_NONE):\n',
                            '    case ZMK_ADV_CONN + CURR_ADV(ZMK_ADV_CONN):\n    case ZMK_ADV_CONN + CURR_ADV(ZMK_ADV_NONE):\n',1)
    anchor = 'K_WORK_DEFINE(update_advertising_work, update_advertising_callback);'
    recovery = '''

/* roBa: reconcile advertising every five seconds, without disconnecting a host
 * or changing the user's selected profile. bt_le_adv_start is idempotent via
 * -EALREADY when advertising is already running. Retry transient failures and
 * stale application advertising state; never stop/restart healthy advertising.
 */
BUILD_ASSERT(!IS_ENABLED(CONFIG_BT_EXT_ADV), "roBa recovery reviewed for legacy advertising only");
static void roba_adv_recovery_callback(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(roba_adv_recovery_work, roba_adv_recovery_callback);

static void roba_adv_recovery_callback(struct k_work *work) {
    if (!zmk_ble_active_profile_is_connected()) {
        update_advertising();
    }
    k_work_reschedule(&roba_adv_recovery_work, K_SECONDS(5));
}
'''
    assert source.count(anchor) == 1
    source = source.replace(anchor,anchor+recovery)
    anchor = '    update_advertising();\n}\n\nstatic int zmk_ble_complete_startup(void)'
    assert source.count(anchor) == 1
    source = source.replace(anchor,'    update_advertising();\n    k_work_reschedule(&roba_adv_recovery_work, K_SECONDS(5));\n}\n\nstatic int zmk_ble_complete_startup(void)')
    return source

if __name__ == '__main__':
    path = Path(sys.argv[1]);before=path.read_text();after=patch(before);path.write_text(after)
    print('roBa advertising recovery patch applied:',hashlib.sha256(after.encode()).hexdigest())
