from pathlib import Path
import importlib.util,subprocess,tempfile,sys
spec=importlib.util.spec_from_file_location('p',Path(__file__).with_name('patch_split_bounds.py'));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
root=Path(sys.argv[1]);original=(root/'central.c').read_text();fixed=p.patch_handler(original);bt=p.patch_bt((root/'bluetooth/central.c').read_text());assert p.patch_handler(fixed)==fixed and p.patch_bt(bt)==bt
header=r'''
#include <stdint.h>
#include <errno.h>
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define IS_ENABLED(x) (x)
#define CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING 1
#define CONFIG_ZMK_INPUT_SPLIT 0
#define ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_BATTERY_EVENT 1
#define LOG_DBG(...) ((void)0)
#define LOG_WRN(...) ((void)0)
#define K_NO_WAIT 0
#define BT_ADDR_LE_STR_LEN 32
static uint8_t peripheral_battery_levels[1];
struct zmk_peripheral_battery_state_changed {uint8_t source,state_of_charge;};
struct event {int type;union {struct {uint8_t level;} battery_event;} data;};
struct peripheral_event_wrapper {uint8_t source;struct event event;};
struct bt_conn {int slot;};
static int released,scanned,queued;
static int peripheral_event_msgq,peripheral_event_work,notify_status_work;
static int raise_zmk_peripheral_battery_state_changed(struct zmk_peripheral_battery_state_changed e){return 0;}
static void bt_addr_le_to_str(int a,char*b,size_t n){}
static int bt_conn_get_dst(struct bt_conn*c){return 0;}
static int peripheral_slot_index_for_conn(struct bt_conn*c){return c->slot;}
static int release_peripheral_slot_for_conn(struct bt_conn*c){released++;return 0;}
static int k_msgq_put(int*q,struct peripheral_event_wrapper*e,int t){assert(e->source==0);queued++;return 0;}
static int k_work_submit(int*w){return 0;}
static int start_scanning(void){scanned++;return 0;}
'''
def battery_handler(s):
 start=s.index('    case ZMK_SPLIT_TRANSPORT_PERIPHERAL_EVENT_TYPE_BATTERY_EVENT: {');end=s.index('#endif',start)
 return 'static int handle(uint8_t source, struct event ev) {switch(ev.type){\n'+s[start:end]+'}\nreturn -1;}\n'
a=bt.index('static void split_central_disconnected(');b=bt.index('static void split_central_security_changed(',a);callback=bt[a:b]
tests=r'''
int main(void){
 struct event e={.type=1,.data.battery_event.level=82};
 assert(handle(0,e)==0&&peripheral_battery_levels[0]==82);
 assert(handle(1,e)==-EINVAL);assert(handle(234,e)==-EINVAL);
 assert(peripheral_battery_levels[0]==82);
 struct bt_conn host={.slot=-EINVAL},left={.slot=0};
 split_central_disconnected(&host,0x13);assert(released==0&&scanned==0&&queued==0);
 split_central_disconnected(&left,0x08);assert(released==1&&scanned==1&&queued==1);
 puts("PASS: invalid battery indices rejected; host disconnect ignored; left disconnect still releases keys and restarts scan");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp)
 for name,src in [('fixed',fixed),('baseline',original)]:
  c=d/(name+'.c');exe=d/name;c.write_text(header+battery_handler(src)+callback+tests)
  subprocess.run(['cc','-std=c11','-fsanitize=undefined','-fno-sanitize-recover=all',str(c),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],text=True,capture_output=True)
  if name=='fixed':assert r.returncode==0,r.stderr;print(r.stdout.strip())
  else:assert r.returncode!=0 and 'out of bounds' in r.stderr,r.stderr;print('PASS: baseline reproduces out-of-bounds access under UndefinedBehaviorSanitizer')
