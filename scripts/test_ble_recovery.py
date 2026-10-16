"""Compile the actual patched advertising code against a deterministic BLE stub."""
from pathlib import Path
import importlib.util,subprocess,tempfile,sys
spec=importlib.util.spec_from_file_location('patch',Path(__file__).with_name('patch_ble_recovery.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
original=Path(sys.argv[1]).read_text();s=m.patch(original);assert m.patch(s)==s
try:m.patch(original+'\n')
except AssertionError:pass
else:raise AssertionError('Unreviewed source accepted')
section=s[s.index('#define CHECKED_ADV_STOP()'):s.index('static void clear_profile_bond')]
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
typedef int bt_addr_le_t;
struct bt_conn {};
struct k_work {int unused;};
static int active_profile,starts,stops,scheduled,error_once;
static bool connected[5],opened[5],on_air;
enum advertising_type {ZMK_ADV_NONE,ZMK_ADV_DIR,ZMK_ADV_CONN} advertising_status;
#define BUILD_ASSERT(cond, msg) _Static_assert(cond, msg)
#define IS_ENABLED(x) (x)
#define CONFIG_BT_EXT_ADV 0
#define CURR_ADV(x) ((x)<<4)
#define LOG_ERR(...) ((void)0)
#define LOG_DBG(...) ((void)0)
#define ARRAY_SIZE(x) 1
#define BT_ID_DEFAULT 0
#define ZMK_ADV_CONN_NAME 0
#define BT_LE_ADV_CONN_DIR_LOW_DUTY(x) 0
#define K_WORK_DEFINE(name,cb) struct k_work name
#define K_WORK_DELAYABLE_DEFINE(name,cb) struct k_work name
#define K_SECONDS(n) (n)
static int zmk_ble_ad[1];
static bool zmk_ble_active_profile_is_connected(void){return connected[active_profile];}
static bool zmk_ble_active_profile_is_open(void){return opened[active_profile];}
static bt_addr_le_t *zmk_ble_active_profile_addr(void){return &active_profile;}
static struct bt_conn *bt_conn_lookup_addr_le(int a,bt_addr_le_t *b){return NULL;}
static void bt_conn_unref(struct bt_conn *c){}
static int bt_le_adv_stop(void){stops++;on_air=false;return 0;}
static int bt_le_adv_start(int p,void *a,int n,void *b,int z){
 starts++;if(error_once){int e=error_once;error_once=0;return e;}
 if(on_air)return -EALREADY;on_air=true;return 0;
}
static int k_work_reschedule(struct k_work *w,int sec){assert(sec==5);scheduled++;return 0;}
'''
test=r'''
int main(void){
 // Failed initial restart: retry after temporary resource exhaustion.
 error_once=-ENOMEM;assert(update_advertising()==-ENOMEM);assert(!on_air);
 roba_adv_recovery_callback(NULL);assert(on_air);assert(advertising_status==ZMK_ADV_CONN);
 // Healthy advertisements are not stopped or restarted by reconciliation.
 int stop_before=stops;roba_adv_recovery_callback(NULL);assert(on_air);assert(stops==stop_before);
 // Stale application state must not suppress an actual restart.
 on_air=false;assert(advertising_status==ZMK_ADV_CONN);
 roba_adv_recovery_callback(NULL);assert(on_air);
 // A connected selected host receives no advertising operations.
 connected[0]=true;int before=starts;roba_adv_recovery_callback(NULL);assert(starts==before);
 // An intentional switch to another connected host is preserved.
 active_profile=2;connected[2]=true;roba_adv_recovery_callback(NULL);assert(starts==before&&active_profile==2);
 // A disconnected selected host is retried without changing the selection.
 connected[2]=false;on_air=false;error_once=-EAGAIN;
 roba_adv_recovery_callback(NULL);assert(!on_air&&active_profile==2);
 roba_adv_recovery_callback(NULL);assert(on_air&&active_profile==2);
 // Open pairing profile stays selected, no forced switch to profile zero.
 active_profile=4;opened[4]=true;on_air=false;
 roba_adv_recovery_callback(NULL);assert(on_air&&active_profile==4);
 assert(stops==stop_before);assert(scheduled==8);
 puts("PASS: transient failures, stale state, healthy advertising, connected hosts, manual profile selection, recurring retry");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.c').write_text(header+section+test)
 subprocess.run(['cc','-std=c11','-Werror=implicit-function-declaration',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: source hash guard and patch idempotence')
