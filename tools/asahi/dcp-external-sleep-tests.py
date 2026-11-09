#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only OR MIT
"""Host checks for the external display processor's system sleep policy.

Extracts dcp_external_sleep_vetoed() (and dcp_external_sleep_strict() when
present) from dcp.c and runs it against a matrix of processor states:

- a starting firmware always keeps the system awake;
- a direct DP-alt or HDMI display, lit or not, lets the system sleep;
- a display over a Thunderbolt tunnel keeps the system awake (#162);
- external_sleep_veto=1 restores the refusal for any attached display;
- a failed processor never refuses sleep;
- the manual (non-native) path is unchanged.

--source PATH checks another copy of dcp.c, e.g. the tree before the change,
which must fail the direct-display cases.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'drivers/gpu/drm/apple/dcp.c'


def function(source, signature):
    start = source.index(signature)
    end = source.index('\n}\n', start) + 3
    return source[start:end]


def extract(source):
    body = ''
    if 'static bool dcp_external_sleep_strict(struct apple_dcp *dcp)' in source:
        body += function(source, 'static bool dcp_external_sleep_strict(struct apple_dcp *dcp)')
    body += function(source, 'static const char *dcp_external_sleep_vetoed(struct apple_dcp *dcp)')
    return body


PREFIX = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define READ_ONCE(x) (x)
#define lockdep_assert_held(x) ((void)(x))
#define dev_info(dev, ...) ((void)(dev))
struct apple_dcp_typec_route { bool tunnel; };
struct apple_dcp_v14 { int unused; };
struct apple_dcp {
	bool external_native;
	int external_requested;
	void *rtk;
	struct apple_dcp_v14 *v14;
	struct apple_dcp_typec_route *active_typec_route;
	bool typec_cable_connected;
	void *hdmi_hpd;
	void *dev;
	int hpd_mutex;
	/* test inputs */
	const char *busy;
	bool starting, failed, hpd_high, rtkit_running, scanout_requested;
};
static int atomic_read(const int *v) { return *v; }
static bool apple_rtkit_is_running(void *rtk) { return rtk != NULL; }
static bool dcpext_scanout_requested(struct apple_dcp *dcp) { return dcp->scanout_requested; }
static struct apple_dcp *current;
static const char *iomfb_v14_7_external_busy(struct apple_dcp *dcp) { return dcp->busy; }
static bool iomfb_v14_7_external_starting(struct apple_dcp *dcp) { return dcp->starting; }
static bool iomfb_v14_7_external_failed(struct apple_dcp *dcp) { return dcp->failed; }
static int gpiod_get_value_cansleep(void *gpio) { (void)gpio; return current->hpd_high; }
static bool external_sleep_veto;
'''

TESTS = r'''
static struct apple_dcp_typec_route direct = { .tunnel = false }, tunnel = { .tunnel = true };
static int hpd_gpio;

static struct apple_dcp native(void)
{
	struct apple_dcp d = { .external_native = true };
	return d;
}

static const char *veto(struct apple_dcp *d)
{
	current = d;
	return dcp_external_sleep_vetoed(d);
}

#define SLEEPS(d) do { const char *w = veto(&(d)); if (w) { printf("unexpected refusal: %s (line %d)\n", w, __LINE__); return 1; } } while (0)
#define REFUSES(d) do { if (!veto(&(d))) { printf("expected a refusal (line %d)\n", __LINE__); return 1; } } while (0)

int main(void)
{
	struct apple_dcp d;

	/* Idle, nothing attached: sleeps (unchanged). */
	d = native(); SLEEPS(d);
	/* Firmware starting: always refused. */
	d = native(); d.busy = "its firmware is starting"; d.starting = true; REFUSES(d);
	/* Direct DP-alt display, link up: sleeps. */
	d = native(); d.busy = "a display link is up"; d.active_typec_route = &direct;
	d.typec_cable_connected = true; SLEEPS(d);
	/* Direct DP-alt display attached, link down: sleeps. */
	d = native(); d.active_typec_route = &direct; d.typec_cable_connected = true; SLEEPS(d);
	/* HDMI display attached and lit: sleeps. */
	d = native(); d.hdmi_hpd = &hpd_gpio; d.hpd_high = true; d.busy = "a display link is up"; SLEEPS(d);
	/* Thunderbolt-tunnelled display: refused, link up or not (#162). */
	d = native(); d.busy = "a display link is up"; d.active_typec_route = &tunnel; REFUSES(d);
	d = native(); d.active_typec_route = &tunnel; d.typec_cable_connected = true; REFUSES(d);
	/* external_sleep_veto=1: the old refusal for any attached display. */
	external_sleep_veto = true;
	d = native(); d.active_typec_route = &direct; d.typec_cable_connected = true; REFUSES(d);
	d = native(); d.hdmi_hpd = &hpd_gpio; d.hpd_high = true; REFUSES(d);
	d = native(); d.busy = "a display link is up"; REFUSES(d);
	d = native(); SLEEPS(d);
	external_sleep_veto = false;
	/* A failed processor never refuses sleep, whatever is attached. */
	d = native(); d.failed = true; d.active_typec_route = &direct; d.typec_cable_connected = true; SLEEPS(d);
	/* Manual path: refuses once its firmware was attempted (unchanged). */
	d = (struct apple_dcp){ .external_native = false }; SLEEPS(d);
	d = (struct apple_dcp){ .external_native = false, .external_requested = 1 }; REFUSES(d);
	printf("dcp-external-sleep: PASS\n");
	return 0;
}
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=SOURCE)
    args = parser.parse_args()
    code = PREFIX + extract(args.source.read_text()) + TESTS
    with tempfile.TemporaryDirectory(prefix='dcp-external-sleep-') as temp:
        src = Path(temp) / 'test.c'
        exe = Path(temp) / 'test'
        src.write_text(code)
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Werror', '-Wno-unused-function',
                        '-o', str(exe), str(src)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
