# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2020, Lars Asplund lars.anders.asplund@gmail.com

from os.path import join, dirname
from vunit import (
    VUnit,
    VerificationComponentInterface,
    VerificationComponent,
)
from itertools import product

root = dirname(__file__)

ui = VUnit.from_argv()
ui.add_random()
ui.add_verification_components()
lib = ui.library("vunit_lib")
lib.add_source_files(join(root, "test", "*.vhd"))


def encode(tb_cfg):
    return ",".join(["%s:%s" % (key, str(tb_cfg[key])) for key in tb_cfg])


def gen_wb_tests(obj, *args):
    for dat_width, num_cycles, strobe_prob, ack_prob, stall_prob in product(*args):
        tb_cfg = dict(
            dat_width=dat_width,
            #  TODO remove fixed addr
            adr_width=32,
            strobe_prob=strobe_prob,
            ack_prob=ack_prob,
            stall_prob=stall_prob,
            num_cycles=num_cycles,
        )
        config_name = encode(tb_cfg)
        obj.add_config(name=config_name, generics=dict(encoded_tb_cfg=encode(tb_cfg)))


def gen_avalon_tests(obj, *args):
    for data_width, num_cycles, readdatavalid_prob, waitrequest_prob in product(*args):
        tb_cfg = dict(
            data_width=data_width,
            readdatavalid_prob=readdatavalid_prob,
            waitrequest_prob=waitrequest_prob,
            num_cycles=num_cycles,
        )
        config_name = encode(tb_cfg)
        obj.add_config(name=config_name, generics=dict(encoded_tb_cfg=encode(tb_cfg)))


def gen_avalon_master_tests(obj, *args):
    for (
        transfers,
        readdatavalid_prob,
        waitrequest_prob,
        write_prob,
        read_prob,
    ) in product(*args):
        tb_cfg = dict(
            readdatavalid_prob=readdatavalid_prob,
            waitrequest_prob=waitrequest_prob,
            write_prob=write_prob,
            read_prob=read_prob,
            transfers=transfers,
        )
        config_name = encode(tb_cfg)
        obj.add_config(name=config_name, generics=dict(encoded_tb_cfg=encode(tb_cfg)))


tb_avalon_slave = lib.test_bench("tb_avalon_slave")

for test in tb_avalon_slave.get_tests():
    gen_avalon_tests(test, [32], [1, 2, 64], [1.0, 0.3], [0.0, 0.4])

tb_avalon_master = lib.test_bench("tb_avalon_master")

for test in tb_avalon_master.get_tests():
    if test.name == "wr single rd single":
        gen_avalon_master_tests(test, [1], [1.0], [0.0], [1.0], [1.0])
    else:
        gen_avalon_master_tests(
            test, [64], [1.0, 0.3], [0.0, 0.7], [1.0, 0.3], [1.0, 0.3]
        )

tb_wishbone_slave = lib.test_bench("tb_wishbone_slave")

for test in tb_wishbone_slave.get_tests():
    #  TODO strobe_prob not implemented in slave tb
    gen_wb_tests(test, [8, 32], [1, 64], [1.0], [0.3, 1.0], [0.4, 0.0])


tb_wishbone_master = lib.test_bench("tb_wishbone_master")

for test in tb_wishbone_master.get_tests():
    gen_wb_tests(test, [8, 32], [1, 64], [0.3, 1.0], [0.3, 1.0], [0.4, 0.0])

tb_axi_stream = lib.test_bench("tb_axi_stream")

for id_length in [0, 8]:
    for dest_length in [0, 8]:
        for user_length in [0, 8]:
            for test in tb_axi_stream.get_tests("*check"):
                test.add_config(
                    name="id_l=%d dest_l=%d user_l=%d"
                    % (id_length, dest_length, user_length),
                    generics=dict(
                        g_id_length=id_length,
                        g_dest_length=dest_length,
                        g_user_length=user_length,
                    ),
                )

tb_axi_stream_protocol_checker = lib.test_bench("tb_axi_stream_protocol_checker")

for data_length in [0, 8]:
    for test in tb_axi_stream_protocol_checker.get_tests("*passing*tdata*"):
        test.add_config(
            name="data_length=%d" % data_length, generics=dict(data_length=data_length)
        )

for test in tb_axi_stream_protocol_checker.get_tests("*failing*tid width*"):
    test.add_config(name="dest_length=25", generics=dict(dest_length=25))
    test.add_config(
        name="id_length=8 dest_length=17", generics=dict(id_length=8, dest_length=17)
    )

test_failing_max_waits = tb_axi_stream_protocol_checker.test(
    "Test failing check of that tready comes within max_waits after valid"
)
for max_waits in [0, 8]:
    test_failing_max_waits.add_config(
        name="max_waits=%d" % max_waits, generics=dict(max_waits=max_waits)
    )

test_lib = ui.add_library("test_lib")

bus_master_vci = VerificationComponentInterface.find(
    lib, "bus_master_pkg", "bus_master_t"
)
bus_master_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "bus_master_pkg", "tb_bus_master_t_compliance_template.vhd"),
)
VerificationComponent.find(lib, "axi_lite_master", bus_master_vci).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_axi_lite_master_compliance_template.vhd"),
)

axi_slave_vci = VerificationComponentInterface.find(lib, "axi_slave_pkg", "axi_slave_t")
axi_slave_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "axi_slave_pkg", "tb_axi_slave_t_compliance_template.vhd"),
)
VerificationComponent.find(lib, "axi_read_slave", axi_slave_vci).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_axi_read_slave_compliance_template.vhd"),
)

axi_stream_master_vci = VerificationComponentInterface.find(
    lib, "axi_stream_pkg", "axi_stream_master_t"
)
axi_stream_master_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(
        root, ".vc", "axi_stream_pkg", "tb_axi_stream_master_t_compliance_template.vhd"
    ),
)
VerificationComponent.find(
    lib, "axi_stream_master", axi_stream_master_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_axi_stream_master_compliance_template.vhd"),
)

axi_stream_slave_vci = VerificationComponentInterface.find(
    lib, "axi_stream_pkg", "axi_stream_slave_t"
)
axi_stream_slave_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(
        root, ".vc", "axi_stream_pkg", "tb_axi_stream_slave_t_compliance_template.vhd"
    ),
)
VerificationComponent.find(
    lib, "axi_stream_slave", axi_stream_slave_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_axi_stream_slave_compliance_template.vhd"),
)

axi_stream_monitor_vci = VerificationComponentInterface.find(
    lib, "axi_stream_pkg", "axi_stream_monitor_t"
)
axi_stream_monitor_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(
        root, ".vc", "axi_stream_pkg", "tb_axi_stream_monitor_t_compliance_template.vhd"
    ),
)
VerificationComponent.find(
    lib, "axi_stream_monitor", axi_stream_monitor_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_axi_stream_monitor_compliance_template.vhd"),
)

axi_stream_protocol_checker_vci = VerificationComponentInterface.find(
    lib, "axi_stream_pkg", "axi_stream_protocol_checker_t"
)
axi_stream_protocol_checker_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(
        root,
        ".vc",
        "axi_stream_pkg",
        "tb_axi_stream_protocol_checker_t_compliance_template.vhd",
    ),
)
VerificationComponent.find(
    lib, "axi_stream_protocol_checker", axi_stream_protocol_checker_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_axi_stream_protocol_checker_compliance_template.vhd"),
)

uart_master_vci = VerificationComponentInterface.find(lib, "uart_pkg", "uart_master_t")
uart_master_vci.add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)
VerificationComponent.find(lib, "uart_master", uart_master_vci).add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)

uart_slave_vci = VerificationComponentInterface.find(lib, "uart_pkg", "uart_slave_t")
uart_slave_vci.add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)
VerificationComponent.find(lib, "uart_slave", uart_slave_vci).add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)

wishbone_master_vci = VerificationComponentInterface.find(
    lib, "wishbone_pkg", "wishbone_master_t"
)
wishbone_master_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "wishbone_pkg", "tb_wishbone_master_t_compliance_template.vhd",),
)
VerificationComponent.find(
    lib, "wishbone_master", wishbone_master_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_wishbone_master_compliance_template.vhd"),
)

wishbone_slave_vci = VerificationComponentInterface.find(
    lib, "wishbone_pkg", "wishbone_slave_t"
)
wishbone_slave_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "wishbone_pkg", "tb_wishbone_slave_t_compliance_template.vhd",),
)
VerificationComponent.find(
    lib, "wishbone_slave", wishbone_slave_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_wishbone_slave_compliance_template.vhd"),
)

std_logic_checker_vci = VerificationComponentInterface.find(
    lib, "signal_checker_pkg", "signal_checker_t"
)
std_logic_checker_vci.add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)
VerificationComponent.find(
    lib, "std_logic_checker", std_logic_checker_vci
).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_std_logic_checker_compliance_template.vhd"),
)

ram_master_vci = VerificationComponentInterface.find(
    lib, "ram_master_pkg", "ram_master_t"
)
ram_master_vci.add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "ram_master_pkg", "tb_ram_master_t_compliance_template.vhd",),
)
VerificationComponent.find(lib, "ram_master", ram_master_vci).add_vhdl_testbench(
    test_lib,
    join(root, "compliance_test"),
    join(root, ".vc", "tb_ram_master_compliance_template.vhd"),
)

VerificationComponentInterface.find(
    lib, "stream_master_pkg", "stream_master_t"
).add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)

VerificationComponentInterface.find(
    lib, "stream_slave_pkg", "stream_slave_t"
).add_vhdl_testbench(
    test_lib, join(root, "compliance_test"),
)

ui.set_compile_option("rivierapro.vcom_flags", ["-dbg"])

ui.main()
