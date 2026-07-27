# Auto-drafted runbook entries

Generated at `1785144249692` (UTC ms).  
Each section below is **a draft** assembled from oncall corrections (`verdict ∈ thumbs_down|incorrect` with `correct_root_cause` set). Review before merging.

- **45** cluster(s) ready for review
- **217** cluster(s) below the `min_occurrences=5` threshold (suppressed)

---

## `session-store` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **12** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the session-store sidecar

- **agent:** _(not recorded)_
  **oncall:** actually a downstream video-encoder timeout, not session-store
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.session-store.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** restart the sidecar, not the main container

_…and 2 more occurrences_

### Suggested runbook entry

> When `session-store` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in session-store, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `recommend-feed` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream video-encoder timeout, not recommend-feed
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `recommend-feed` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the recommend-feed sidecar**.
>
> Recommended first action: `page the session-store oncall; the real ownership is downstream`

---

## `payments-gateway` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** page the price-cache oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the payments-gateway sidecar
  **action:** disable feature flag svc.payments-gateway.new_path

- **agent:** _(not recorded)_
  **oncall:** actually a downstream price-cache timeout, not payments-gateway
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `payments-gateway` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the payments-gateway sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `checkout-api` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream order-pipeline timeout, not checkout-api
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the checkout-api sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for payments-gateway was filling our partition

### Suggested runbook entry

> When `checkout-api` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in checkout-api, not what the agent said**.
>
> Recommended first action: `increase checkout-api concurrency limit to 2x and re-rate-limit upstream`

---

## `auth-service` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream rate-limiter-edge timeout, not auth-service
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for notification-fanout was filling our partition
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream payments-gateway timeout, not auth-service
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream video-encoder timeout, not auth-service
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream cdn-router timeout, not auth-service
  **action:** restart the sidecar, not the main container

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said

### Suggested runbook entry

> When `auth-service` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **actually a downstream rate-limiter-edge timeout, not auth-service**.
>
> Recommended first action: `disable feature flag svc.auth-service.new_path`

---

## `inventory-sync` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **9** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for price-cache was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** disable feature flag svc.inventory-sync.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** page the cart-service oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `inventory-sync` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in inventory-sync, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `image-thumbnail` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **8** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream cdn-router timeout, not image-thumbnail
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for image-thumbnail was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said
  **action:** disable feature flag svc.image-thumbnail.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in image-thumbnail, not what the agent said

- **agent:** _(not recorded)_
  **oncall:** actually a downstream promo-engine timeout, not image-thumbnail
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `image-thumbnail` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in image-thumbnail, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `price-cache` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **8** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.price-cache.new_path

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** disable feature flag svc.price-cache.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream user-profile timeout, not price-cache
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the price-cache sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in price-cache, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** disable feature flag svc.price-cache.new_path

### Suggested runbook entry

> When `price-cache` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `session-store` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** actually a downstream inventory-sync timeout, not session-store
  **action:** page the comment-svc oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream promo-engine timeout, not session-store
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** page the recommend-feed oncall; the real ownership is downstream

### Suggested runbook entry

> When `session-store` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **actually a downstream inventory-sync timeout, not session-store**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `ad-bidder` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream order-pipeline timeout, not ad-bidder
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the ad-bidder sidecar

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.ad-bidder.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in ad-bidder, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `ad-bidder` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase ad-bidder concurrency limit to 2x and re-rate-limit upstream`

---

## `search-suggest` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the search-suggest sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream payments-gateway timeout, not search-suggest

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the search-suggest sidecar
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for image-thumbnail was filling our partition
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `search-suggest` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the search-suggest sidecar**.
>
> Recommended first action: `page the payments-gateway oncall; the real ownership is downstream`

---

## `video-encoder` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream rate-limiter-edge timeout, not video-encoder

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream payments-gateway timeout, not video-encoder
  **action:** disable feature flag svc.video-encoder.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the video-encoder sidecar
  **action:** page the promo-engine oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for search-suggest was filling our partition

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the notification-fanout oncall; the real ownership is downstream

### Suggested runbook entry

> When `video-encoder` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **actually a downstream rate-limiter-edge timeout, not video-encoder**.
>
> Recommended first action: `disable feature flag svc.video-encoder.new_path`

---

## `promo-engine` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** {svc} health-check failure cascade
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** page the auth-service oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream cart-service timeout, not promo-engine

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** page the search-suggest oncall; the real ownership is downstream

### Suggested runbook entry

> When `promo-engine` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the promo-engine sidecar**.
>
> Recommended first action: `increase promo-engine concurrency limit to 2x and re-rate-limit upstream`

---

## `recommend-feed` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in recommend-feed, not what the agent said
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in recommend-feed, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** disable feature flag svc.recommend-feed.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream video-encoder timeout, not recommend-feed
  **action:** page the notification-fanout oncall; the real ownership is downstream

### Suggested runbook entry

> When `recommend-feed` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in recommend-feed, not what the agent said**.
>
> Recommended first action: `increase recommend-feed concurrency limit to 2x and re-rate-limit upstream`

---

## `notification-fanout` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **7** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** {svc} health-check failure cascade
  **oncall:** actually a downstream recommend-feed timeout, not notification-fanout
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.notification-fanout.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream promo-engine timeout, not notification-fanout

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** increase notification-fanout concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `notification-fanout` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the notification-fanout sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `cdn-router` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **7** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** disable feature flag svc.cdn-router.new_path

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream cart-service timeout, not cdn-router
  **action:** page the inventory-sync oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

### Suggested runbook entry

> When `cdn-router` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `auth-service` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream price-cache timeout, not auth-service
  **action:** page the payments-gateway oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for comment-svc was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase auth-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** disable feature flag svc.auth-service.new_path

### Suggested runbook entry

> When `auth-service` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **actually a downstream price-cache timeout, not auth-service**.
>
> Recommended first action: `increase auth-service concurrency limit to 2x and re-rate-limit upstream`

---

## `image-thumbnail` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** increase image-thumbnail concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `image-thumbnail` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **DNS resolution lag in the image-thumbnail sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `ad-bidder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** {svc} health-check failure cascade
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream price-cache timeout, not ad-bidder
  **action:** increase ad-bidder concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream price-cache timeout, not ad-bidder

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the ad-bidder sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the session-store oncall; the real ownership is downstream

### Suggested runbook entry

> When `ad-bidder` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `video-encoder` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the video-encoder sidecar

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the video-encoder oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the video-encoder sidecar

- **agent:** _(not recorded)_
  **oncall:** actually a downstream comment-svc timeout, not video-encoder
  **action:** page the cart-service oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in video-encoder, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream session-store timeout, not video-encoder
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `video-encoder` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the video-encoder sidecar**.
>
> Recommended first action: `page the video-encoder oncall; the real ownership is downstream`

---

## `session-store` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.session-store.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in session-store, not what the agent said
  **action:** increase session-store concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream user-profile timeout, not session-store
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the session-store sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

### Suggested runbook entry

> When `session-store` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in session-store, not what the agent said**.
>
> Recommended first action: `increase session-store concurrency limit to 2x and re-rate-limit upstream`

---

## `promo-engine` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

### Suggested runbook entry

> When `promo-engine` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in promo-engine, not what the agent said**.
>
> Recommended first action: `increase promo-engine concurrency limit to 2x and re-rate-limit upstream`

---

## `price-cache` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for image-thumbnail was filling our partition
  **action:** disable feature flag svc.price-cache.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream cdn-router timeout, not price-cache
  **action:** disable feature flag svc.price-cache.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in price-cache, not what the agent said

- **agent:** {svc} health-check failure cascade
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the notification-fanout oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the price-cache sidecar

### Suggested runbook entry

> When `price-cache` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `disable feature flag svc.price-cache.new_path`

---

## `recommend-feed` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the recommend-feed sidecar
  **action:** increase recommend-feed concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in recommend-feed, not what the agent said
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** page the search-suggest oncall; the real ownership is downstream

### Suggested runbook entry

> When `recommend-feed` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `session-store` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the session-store sidecar
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in session-store, not what the agent said

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for session-store was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.session-store.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream ad-bidder timeout, not session-store
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for recommend-feed was filling our partition
  **action:** page the inventory-sync oncall; the real ownership is downstream

### Suggested runbook entry

> When `session-store` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **DNS resolution lag in the session-store sidecar**.
>
> Recommended first action: `page the checkout-api oncall; the real ownership is downstream`

---

## `promo-engine` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream session-store timeout, not promo-engine
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the promo-engine sidecar
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream cart-service timeout, not promo-engine
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase promo-engine concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `promo-engine` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **feature flag flipped to 100% an hour earlier; not a deploy regression**.
>
> Recommended first action: `increase promo-engine concurrency limit to 2x and re-rate-limit upstream`

---

## `cdn-router` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said
  **action:** disable feature flag svc.cdn-router.new_path

- **agent:** no actionable signal found
  **oncall:** actually a downstream auth-service timeout, not cdn-router
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for promo-engine was filling our partition

- **agent:** no actionable signal found
  **oncall:** actually a downstream live-stream-edge timeout, not cdn-router

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cdn-router sidecar
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `cdn-router` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the cdn-router sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `search-suggest` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **6** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream ad-bidder timeout, not search-suggest
  **action:** page the image-thumbnail oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** page the order-pipeline oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in search-suggest, not what the agent said
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** _(not recorded)_
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase search-suggest concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream image-thumbnail timeout, not search-suggest
  **action:** page the price-cache oncall; the real ownership is downstream

### Suggested runbook entry

> When `search-suggest` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for auth-service was filling our partition**.
>
> Recommended first action: `increase search-suggest concurrency limit to 2x and re-rate-limit upstream`

---

## `order-pipeline` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **6** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the order-pipeline sidecar

- **agent:** no actionable signal found
  **oncall:** actually a downstream inventory-sync timeout, not order-pipeline
  **action:** page the session-store oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream price-cache timeout, not order-pipeline
  **action:** disable feature flag svc.order-pipeline.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said
  **action:** disable feature flag svc.order-pipeline.new_path

### Suggested runbook entry

> When `order-pipeline` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in order-pipeline, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.order-pipeline.new_path`

---

## `comment-svc` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **5**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** actually a downstream live-stream-edge timeout, not comment-svc
  **action:** page the cart-service oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for live-stream-edge was filling our partition
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `comment-svc` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `payments-gateway` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the live-stream-edge oncall; the real ownership is downstream

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** queue head-of-line blocking in payments-gateway, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase payments-gateway concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for user-profile was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `payments-gateway` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in payments-gateway, not what the agent said**.
>
> Recommended first action: `page the live-stream-edge oncall; the real ownership is downstream`

---

## `user-profile` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said

- **agent:** no actionable signal found
  **oncall:** actually a downstream comment-svc timeout, not user-profile
  **action:** disable feature flag svc.user-profile.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for rate-limiter-edge was filling our partition
  **action:** increase user-profile concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the user-profile sidecar

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in user-profile, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `user-profile` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in user-profile, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.user-profile.new_path`

---

## `notification-fanout` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream price-cache timeout, not notification-fanout

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in notification-fanout, not what the agent said
  **action:** page the checkout-api oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the notification-fanout sidecar
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `notification-fanout` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in notification-fanout, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `cdn-router` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream image-thumbnail timeout, not cdn-router
  **action:** disable feature flag svc.cdn-router.new_path

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in cdn-router, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream recommend-feed timeout, not cdn-router
  **action:** increase cdn-router concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream live-stream-edge timeout, not cdn-router
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `cdn-router` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **actually a downstream image-thumbnail timeout, not cdn-router**.
>
> Recommended first action: `disable feature flag svc.cdn-router.new_path`

---

## `image-thumbnail` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the image-thumbnail sidecar
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the image-thumbnail sidecar

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** page the recommend-feed oncall; the real ownership is downstream

### Suggested runbook entry

> When `image-thumbnail` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the image-thumbnail sidecar**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `video-encoder` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** DNS resolution lag in the video-encoder sidecar

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition
  **action:** disable feature flag svc.video-encoder.new_path

- **agent:** no actionable signal found
  **oncall:** actually a downstream session-store timeout, not video-encoder

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** increase video-encoder concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `video-encoder` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition**.
>
> Recommended first action: `disable feature flag svc.video-encoder.new_path`

---

## `auth-service` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **4**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for video-encoder was filling our partition
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.auth-service.new_path

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in auth-service, not what the agent said

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** disable feature flag svc.auth-service.new_path

### Suggested runbook entry

> When `auth-service` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in auth-service, not what the agent said**.
>
> Recommended first action: `restart the sidecar, not the main container`

---

## `comment-svc` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for ad-bidder was filling our partition

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said
  **action:** increase comment-svc concurrency limit to 2x and re-rate-limit upstream

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in comment-svc, not what the agent said

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** actually a downstream notification-fanout timeout, not comment-svc
  **action:** restart the sidecar, not the main container

### Suggested runbook entry

> When `comment-svc` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in comment-svc, not what the agent said**.
>
> Recommended first action: `increase comment-svc concurrency limit to 2x and re-rate-limit upstream`

---

## `cart-service` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said
  **action:** page the user-profile oncall; the real ownership is downstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cart-service sidecar
  **action:** increase cart-service concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the cart-service sidecar

- **agent:** {svc} health-check failure cascade
  **oncall:** queue head-of-line blocking in cart-service, not what the agent said

### Suggested runbook entry

> When `cart-service` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the cart-service sidecar**.
>
> Recommended first action: `page the user-profile oncall; the real ownership is downstream`

---

## `live-stream-edge` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Leak in v{ver} of the request-context middleware
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition
  **action:** page the notification-fanout oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** DNS resolution lag in the live-stream-edge sidecar
  **action:** disable feature flag svc.live-stream-edge.new_path

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cart-service was filling our partition
  **action:** increase live-stream-edge concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `live-stream-edge` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition**.
>
> Recommended first action: `page the notification-fanout oncall; the real ownership is downstream`

---

## `promo-engine` -- pattern: `synthetic-monitor-flap-consecutive`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** disable feature flag svc.promo-engine.new_path

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the promo-engine sidecar

- **agent:** no actionable signal found
  **oncall:** actually a downstream ad-bidder timeout, not promo-engine
  **action:** disable feature flag svc.promo-engine.new_path

- **agent:** no actionable signal found
  **oncall:** feature flag flipped to 100% an hour earlier; not a deploy regression
  **action:** restart the sidecar, not the main container

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in promo-engine, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `promo-engine` fires `synthetic-monitor-flap-consecutive`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in promo-engine, not what the agent said**.
>
> Recommended first action: `disable feature flag svc.promo-engine.new_path`

---

## `inventory-sync` -- pattern: `latency-spiking-checkout-error`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** Redis connection pool exhaustion under load
  **oncall:** shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** queue head-of-line blocking in inventory-sync, not what the agent said
  **action:** increase inventory-sync concurrency limit to 2x and re-rate-limit upstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** DNS resolution lag in the inventory-sync sidecar
  **action:** page the cdn-router oncall; the real ownership is downstream

- **agent:** _(not recorded)_
  **oncall:** actually a downstream image-thumbnail timeout, not inventory-sync
  **action:** restart the sidecar, not the main container

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream order-pipeline timeout, not inventory-sync
  **action:** disable feature flag svc.inventory-sync.new_path

### Suggested runbook entry

> When `inventory-sync` fires `latency-spiking-checkout-error`-shaped alerts, the most common true root cause is: **shared-tenant noisy-neighbor: kafka topic for inventory-sync was filling our partition**.
>
> Recommended first action: `increase inventory-sync concurrency limit to 2x and re-rate-limit upstream`

---

## `order-pipeline` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **3**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** actually a downstream cdn-router timeout, not order-pipeline
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** actually a downstream video-encoder timeout, not order-pipeline
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the order-pipeline sidecar
  **action:** increase order-pipeline concurrency limit to 2x and re-rate-limit upstream

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for cdn-router was filling our partition

- **agent:** no actionable signal found
  **oncall:** queue head-of-line blocking in order-pipeline, not what the agent said
  **action:** no-op; this is a known flaky synthetic monitor

### Suggested runbook entry

> When `order-pipeline` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **actually a downstream cdn-router timeout, not order-pipeline**.
>
> Recommended first action: `increase order-pipeline concurrency limit to 2x and re-rate-limit upstream`

---

## `comment-svc` -- pattern: `noisy-probe-alert-briefly`

- Occurrences: **5** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** disable feature flag svc.comment-svc.new_path

- **agent:** _(not recorded)_
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** DNS resolution lag in the comment-svc sidecar
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** no actionable signal found
  **oncall:** shared-tenant noisy-neighbor: kafka topic for checkout-api was filling our partition

### Suggested runbook entry

> When `comment-svc` fires `noisy-probe-alert-briefly`-shaped alerts, the most common true root cause is: **DNS resolution lag in the comment-svc sidecar**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

## `checkout-api` -- pattern: `xx-rate-sustained-deploy`

- Occurrences: **5** -- distinct submitters: **2**

### What the agent kept saying (and what oncall corrected)

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** page the search-suggest oncall; the real ownership is downstream

- **agent:** Redis connection pool exhaustion under load
  **oncall:** actually a downstream auth-service timeout, not checkout-api
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** _(not recorded)_
  **oncall:** actually a downstream notification-fanout timeout, not checkout-api
  **action:** no-op; this is a known flaky synthetic monitor

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** queue head-of-line blocking in checkout-api, not what the agent said
  **action:** disable feature flag svc.checkout-api.new_path

- **agent:** Recent deploy introduced a null-pointer in checkout flow
  **oncall:** shared-tenant noisy-neighbor: kafka topic for order-pipeline was filling our partition
  **action:** increase checkout-api concurrency limit to 2x and re-rate-limit upstream

### Suggested runbook entry

> When `checkout-api` fires `xx-rate-sustained-deploy`-shaped alerts, the most common true root cause is: **queue head-of-line blocking in checkout-api, not what the agent said**.
>
> Recommended first action: `no-op; this is a known flaky synthetic monitor`

---

