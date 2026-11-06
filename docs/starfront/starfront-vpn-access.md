# Starfront WireGuard VPN: Access From Home (Windows)

Tested and working from Brett's Windows PC in the UK, 6 Nov 2026. This answers the open checklist question "what owners can actually control over the WireGuard VPN" for file access. Seestar app control over the VPN is still untested (Starfront's requirements say S30/S50 cannot be controlled directly over VPN); the Mac mini stays the control route.

## The config (from Starfront, 6 Nov 2026)

- File: BrettJohnson-B15.conf (contains the private key: keep it in the password manager, never share it)
- My VPN address: **10.15.250.16**
- Endpoint: 74.84.11.76:51820, MTU 1280, PersistentKeepalive 25
- AllowedIPs (split tunnel, only these go over the VPN):
  - **10.15.10.212**: my Seestar S50 Pro
  - **172.16.5.21**: Starfront customer share (roof, weather, images)
- The Mac mini is NOT in AllowedIPs. Reach it with RustDesk as before
- **One device at a time.** Do not run the same config on two devices at once (Starfront's instruction). Do NOT install it on the Mac mini: it is already on site

## Setup on Windows

1. Install WireGuard from wireguard.com/install
2. Import tunnel(s) from file (the zip or the .conf), then Activate
3. Check Latest handshake is recent and data is received

## Windows needs guest SMB enabled (one-off, admin PowerShell)

Windows 11 blocks guest logins to file shares by default (error 1272). In PowerShell **run as administrator**:

```
Set-SmbClientConfiguration -EnableInsecureGuestLogons $true -RequireSecuritySignature $false
```

This lowers protection for all network shares on the PC. To undo: `Set-SmbClientConfiguration -EnableInsecureGuestLogons $false -RequireSecuritySignature $true`

## Connecting to the shares

Roof and weather share (guest / guest):
```
net use \\172.16.5.21\sfro-customer /user:guest guest
dir \\172.16.5.21\sfro-customer
```
Folders: images, roof, weather.

Seestar share (guest, **blank** password). Without the guest login first, Windows tries the Windows account and gets error 5 Access Denied:
```
net use \\10.15.10.212\IPC$ /user:guest ""
net use "\\10.15.10.212\EMMC Images" /user:guest ""
dir "\\10.15.10.212\EMMC Images\MyWorks"
```
The Seestar runs Samba 4.19.5 with one share, **EMMC Images**, containing **darklibrary** and **MyWorks**. MyWorks holds one folder per target plus a matching **_sub** folder for the FITS subs (e.g. "M 42_mosaic" and "M 42_mosaic_sub").

## Test results, 6 Nov 2026

| Test | Result |
|---|---|
| Ping Seestar 10.15.10.212 | OK, 125 to 236 ms |
| Ping share 172.16.5.21 | OK, about 116 ms |
| Port 445 on both | Open |
| sfro-customer share | Opened as guest after the admin SMB change |
| Seestar EMMC Images share | Opened as guest with blank password. No Starfront ticket needed for VPN access |

## Copying subs home

- Use robocopy, not drag and drop: it resumes after a dropped tunnel and skips files already copied
```
robocopy "\\10.15.10.212\EMMC Images\MyWorks" "D:\Starfront\MyWorks" *.fit /S /Z /R:3 /W:10
```
- Change the destination to wherever the FITS importer expects files
- Transfer in Texas daytime, never while the scope is imaging. Latency is 120 to 230 ms, so large nights take a while

## Still open

- Seestar app control from home over the VPN (expected not to work; untested)
- SMB from the Mac mini on site still goes through Starfront's firewall rule (ticket); ask whether the Seestar's IP is reserved
