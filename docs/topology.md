# Reference Topology (the live demo lab)

The live demo runs against **four Arista EOS switches in a full mesh**, running **two
protocols at once**: OSPF (single area 0) carries the transit links, and a full mesh of
**eBGP** sessions advertises the loopbacks. Every switch holds a `FULL` OSPF adjacency *and*
an `Established` eBGP session with the other three.

> **Note on addresses:** the management/SSH addresses are environment-specific and live
> only in your git-ignored `inventory.local.yaml` (see [real-lab.md](real-lab.md)).
> The addresses below are the in-fabric OSPF/loopback addresses (RFC 1918) and are safe to
> share. Do not put your real management subnet in this file.

```text
            SW1 (10.255.0.1)
           /      |       \
   10.12.12/24  10.13.13/24  10.14.14/24
        /         |           \
     SW2 ------10.23.23/24------ SW3
   (10.255.0.2)      \         /  (10.255.0.3)
        \         10.24.24/24 10.34.34/24
         \____________|_______/
                     SW4 (10.255.0.4)
```

**Routers / router IDs** (each switch's `Loopback0` doubles as its OSPF + BGP router ID):

| Switch | Platform | Loopback0 / Router ID | OSPF process / area | BGP AS |
| --- | --- | --- | --- | --- |
| SW1 | `arista_eos` | `10.255.0.1/32` | 1 / area 0 | `65001` |
| SW2 | `arista_eos` | `10.255.0.2/32` | 1 / area 0 | `65002` |
| SW3 | `arista_eos` | `10.255.0.3/32` | 1 / area 0 | `65003` |
| SW4 | `arista_eos` | `10.255.0.4/32` | 1 / area 0 | `65004` |

**Two-node transit segments** (six `/24` links, full mesh — each segment connects exactly
two switches; OSPF runs them as its default broadcast network type, so you'll see a DR/BDR
elected on each):

| Link | Subnet | A-side | B-side |
| --- | --- | --- | --- |
| SW1–SW2 | `10.12.12.0/24` | SW1 `Et1` .1 | SW2 `Et1` .2 |
| SW1–SW3 | `10.13.13.0/24` | SW1 `Et2` .1 | SW3 `Et2` .3 |
| SW1–SW4 | `10.14.14.0/24` | SW1 `Et3` .1 | SW4 `Et3` .4 |
| SW2–SW3 | `10.23.23.0/24` | SW2 `Et3` .2 | SW3 `Et3` .3 |
| SW2–SW4 | `10.24.24.0/24` | SW2 `Et2` .2 | SW4 `Et2` .4 |
| SW3–SW4 | `10.34.34.0/24` | SW3 `Et1` .3 | SW4 `Et1` .4 |

Reachability is split by protocol, which is visible in any switch's `show ip route`: `C` for
the three local transit links and its own loopback, `O` for the three **remote transit
`/24`s** (learned via OSPF), and `B` for the three **remote loopbacks** (the rest of the
`10.255.0.0/24` space, learned via eBGP). The eBGP sessions peer over the directly connected
transit-link addresses — SW1 (`AS 65001`) peers with `10.12.12.2` (`AS 65002`), `10.13.13.3`
(`AS 65003`), and `10.14.14.4` (`AS 65004`).

Adding a demo loopback with `configure_device` and watching it propagate is a clean way to
show a real change end-to-end: advertise it into OSPF and it appears as `O` on the neighbors,
or originate it with a BGP `network` statement and it appears as `B`.
