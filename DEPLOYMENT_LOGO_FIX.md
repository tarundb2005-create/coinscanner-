# CoinScanner Coin Logo Fix - Deployment Guide

## Pre-Deployment Checklist

### Code Review
- [ ] All changes committed and reviewed
- [ ] No hardcoded dev credentials in code
- [ ] CSP policies appropriate for production
- [ ] Debug endpoints `/api/debug/coins` accessible only in dev (optional: add auth)

### Configuration Review
- [ ] CoinGecko API timeout set to 10 seconds (production-safe)
- [ ] Redis cache TTL correct (24h for metadata, 60s for prices)
- [ ] Logger levels set appropriately (INFO for production)
- [ ] No verbose debug logging in production build

### Environment Variables
- [ ] REDIS_URL configured (if using Redis)
- [ ] DATABASE_URL configured for PostgreSQL
- [ ] DEBUG mode disabled in production
- [ ] SENTRY_DSN configured for error tracking

---

## Deployment Steps

### Step 1: Backup Current State
```bash
# Tag current version
git tag -a v1.production.pre-logo-fix -m "Before logo fix"
git push --tags
```

### Step 2: Deploy Code Changes
```bash
# Deploy to production environment
# Using your deployment tool (Railway, Render, etc.)

# Key files changed:
# - services/coingecko.py
# - app.py (build_coin, get_coin_metadata, CSP, debug endpoint)
# - static/js/coins.js (image fallback)
```

### Step 3: Clear Caches
```bash
# Redis flush to clear old metadata
# This forces fresh logo loading on first page load
redis-cli FLUSHDB

# Or if specific keys:
redis-cli DEL cache:metadata cache:prices cache:market_movers
```

### Step 4: Verify Deployment
```bash
# Health checks
curl https://coinscanner.yourdom.com/health
curl https://coinscanner.yourdom.com/health/db
curl https://coinscanner.yourdom.com/health/redis

# Debug endpoint (temporarily allow)
curl https://coinscanner.yourdom.com/api/debug/coins | jq .

# Expected: logo_percentage > 80
```

### Step 5: Monitor Production
- [ ] Check application logs for errors
- [ ] Monitor Sentry for new exceptions
- [ ] Check CDN/image loading performance
- [ ] Verify no CSP violations in browser console

---

## Rollback Plan

If issues occur in production:

### Rollback Option 1: Code Rollback
```bash
git revert <commit-hash>
git push
# Redeploy
```

### Rollback Option 2: Disable Logo Loading
If CoinGecko API is causing issues:
1. Set coingecko.load_logos() to no-op (return early)
2. All coins will use fallback images
3. Users still see symbol fallbacks

### Rollback Option 3: Disable Enhanced Metadata
If performance degradation:
1. Reduce CoinGecko fetch from 10 pages to 5
2. Reduce cache TTL from 24h to 6h

---

## Post-Deployment Verification

### Immediate (First hour)
- [ ] Home page loads without errors
- [ ] Coins page displays logos correctly
- [ ] Debug endpoint shows healthy stats
- [ ] No new errors in logs

### Short-term (First 24 hours)
- [ ] Monitor cache hit rates
- [ ] Check average response times
- [ ] Verify logo percentage stays >80%
- [ ] Check user feedback channels

### Long-term (Weekly)
- [ ] Monitor CDN performance
- [ ] Review CoinGecko API rate limits
- [ ] Check for any 404 image errors
- [ ] Verify cache refresh is working

---

## Performance Metrics to Track

### Before & After Comparison
| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Coins with logos | ~70% | >85% | >80% |
| Page load time | <2s | <2s | <3s |
| API debug endpoint response | N/A | <100ms | <200ms |
| Cache hit rate | ~70% | >90% | >85% |

### Key Metrics (New Relic / DataDog)
- `coingecko_logo_load_duration_ms`
- `coins_page_image_load_success_rate`
- `fallback_image_usage_percentage`
- `csp_violations_per_hour`

---

## Support & Troubleshooting

### Issue: "Images not loading, showing symbol fallback"
**Root Cause:** CoinGecko API rate limiting or down
**Solution:**
```python
# Check cache status
curl /api/debug/coins
# If logo_percentage < 50%, investigate CoinGecko connectivity
```

### Issue: "CSP violations in console for images"
**Root Cause:** Image domain not in CSP policy
**Solution:**
1. Check browser console for specific domain
2. Add domain to `TALISMAN_CSP` in app.py
3. Redeploy

### Issue: "High memory usage after deployment"
**Root Cause:** Logo cache growing too large
**Solution:**
```python
# Reduce cache size
# In coingecko.py, reduce pages from 10 to 5
```

### Issue: "Logos showing old/stale images"
**Root Cause:** 24-hour cache not refreshed
**Solution:**
```bash
# Manual cache clear
redis-cli DEL cache:metadata
```

---

## Production Operations

### Regular Maintenance
- [ ] Monitor CoinGecko API quota monthly
- [ ] Review CSP policy quarterly
- [ ] Update fallback logo URLs if hosts change
- [ ] Test rollback procedure quarterly

### Documentation Updates
- [ ] Update architecture docs with logo loading flow
- [ ] Document CSP policy changes
- [ ] Add troubleshooting guide for image issues
- [ ] Update runbook with debug commands

### Team Communication
- [ ] Notify support team of changes
- [ ] Document expected behavior (logos + fallbacks)
- [ ] Create FAQ for "why is my coin showing a symbol"
- [ ] Share debug endpoint access details

---

## Appendix: Debug Commands

```bash
# Check logo cache size
redis-cli INFO memory

# View specific coin logos
curl http://localhost:5000/api/debug/coins | jq '.sample_real_logos'

# Clear all caches
redis-cli FLUSHALL

# View app logs (if using Docker)
docker logs -f coinscanner

# Check CoinGecko connectivity
curl -I https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page=1

# Check image loading via curl
curl -I https://assets.coingecko.com/coins/images/1/large/bitcoin.png
# Should return 200 OK
```

---

## Sign-off

- [ ] Code reviewed and approved
- [ ] Tests passed
- [ ] Performance acceptable
- [ ] Deployment procedure reviewed
- [ ] Rollback plan prepared
- [ ] Monitoring set up
- [ ] Documentation updated

**Deployed By:** _______________  
**Date:** _______________  
**Verified By:** _______________  
**Date:** _______________
