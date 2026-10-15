# Detector provider ownership

The dashboard manages only `autodarts.service` (UI port 3180) and
`cdo-dart-detector.service` (UI port 41975). `autodarts-manager.service` stays running.
The backend must run as root so it can control systemd and write root-owned mode
0600 selection state at `/var/lib/cdo/dashboard/detector-provider.json`.

Install the included `systemd/cdo-dart-detector.service.d/exclusive-provider.conf`
at `/etc/systemd/system/cdo-dart-detector.service.d/exclusive-provider.conf`, then
run `systemctl daemon-reload`. `Conflicts=` prevents both detectors from running;
`After=` orders the old detector's stop before the new detector's start, including
when a service is started outside the dashboard. Keep this drop-in outside vendor
unit directories so package updates preserve it.

Use `POST /api/detectors/switch` with JSON `{"provider":"autodarts"}` or
`{"provider":"cdo"}` from the dashboard's own origin. This stops and disables
the other provider, verifies release, enables and starts the selected provider,
then saves the selection. Only the selected provider is enabled for startup.
The persisted selection is UI preference; live systemd state determines ownership.
`GET /api/detectors` observes state without changing services or creating files.
Foreign browser origins are rejected. Headerless non-browser clients remain usable.

Legacy dashboard Autodarts start/restart endpoints use the same serialized switch
manager, selecting Autodarts explicitly and disabling CDO first. They no longer
start Autodarts by proxying directly to the manager module. Direct local manager
calls remain protected by the systemd conflict drop-in.

The generic `autodarts-manager` module start/restart aliases also use the switch
manager. Dashboard install/update routes (including module aliases and the legacy
Apps install route) require same-origin requests and reject installation while
CDO is selected or running. Select Autodarts before installing or updating it.
This is a practical admission check, not an installer transaction lock; the
systemd drop-in enforces exclusivity if services change during an installer job.

Transitions use a process-wide thread lock and a filesystem flock. Forward work
has a 55-second deadline; rollback has at most 20 seconds and all work is capped
at 80 seconds. Subprocess calls use fixed argv and bounded timeouts. On failure
the prior running/enabled state and selection are restored. An incomplete rollback
returns an explicit error; inspect both units before retrying.
