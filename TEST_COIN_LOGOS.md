# CoinScanner Coin Logo Fix - Test Plan

## Overview
This document outlines comprehensive testing for the coin logo fixes implemented across CoinScanner.

## Phase 1: Backend Validation

### Test 1.1 - API Debug Endpoint
```bash
# Check logo loading stats
curl -X GET http://localhost:5000/api/debug/coins | jq .

# Expected output:
# {
#   "total_coins": ~50,
#   "coins_with_logos": >40,
#   "coins_with_fallback": <10,
#   "logo_percentage": >80,
#   "coingecko_cache_size": ~2500,
#   "sample_real_logos": [...],
#   "sample_fallback_coins": [...],
#   "major_coins_logos": { "BTC": "...", "ETH": "...", "SOL": "..." }
# }
```

### Test 1.2 - Verify CoinGecko Cache Population
Check application logs for:
```
✓ Loaded X CoinGecko logos from API
[METADATA] Coins with logos: X/Y, Fallback: Z
```

### Test 1.3 - Verify CSP Headers
```bash
curl -i http://localhost:5000/coins | grep -i "content-security-policy"

# Expected to include:
# img-src 'self' data: https://assets.coingecko.com https://coin-images.coingecko.com https://assets.coincap.io https://s2.coinmarketcap.com https://www.gstatic.com
```

---

## Phase 2: Frontend Visual Testing

### Test 2.1 - Home Page Logo Display
**URL:** `http://localhost:5000/`
**Checklist:**
- [ ] Ticker strip at top shows coin logos (BTC, ETH, etc.)
- [ ] Each ticker item has a coin image
- [ ] Trending chips show coin logos
- [ ] Market Movers section (gainers/losers/picks) displays coin images
- [ ] Watchlist section shows saved coin logos
- [ ] No broken image icons (alt text shown instead)
- [ ] All images load without console errors

### Test 2.2 - Coins Page - Table View
**URL:** `http://localhost:5000/coins?view=table`
**Checklist:**
- [ ] All coins in table have logo images
- [ ] Logos display in the "Coin" column
- [ ] Images are appropriately sized (32x32 or similar)
- [ ] Fallback: Symbol appears in circle if image fails to load
- [ ] No broken image icons visible
- [ ] Infinite scroll: New rows loaded on scroll have logos
- [ ] Console: No CSP violations or 404 errors for images

### Test 2.3 - Coins Page - Card View
**URL:** `http://localhost:5000/coins?view=card`
**Checklist:**
- [ ] All coins display as cards
- [ ] Each card shows coin logo (larger, ~40x40)
- [ ] Card layout is responsive
- [ ] Fallback symbols appear in circles when images fail
- [ ] No broken image indicators
- [ ] Infinite scroll works with images loading
- [ ] Browser DevTools Network tab shows images loading from correct domains

### Test 2.4 - Coin Detail Page
**URL:** `http://localhost:5000/coin/bitcoin`
**Checklist:**
- [ ] Large coin logo displays in hero section (64x64+)
- [ ] Logo loads without distortion
- [ ] Image quality is good
- [ ] No fallback symbol visible (image should load)
- [ ] Chart and other page elements load normally

### Test 2.5 - Search & Filter
**URL:** `http://localhost:5000/coins`
**Actions:**
- [ ] Type "bitcoin" in search box
- [ ] Results show BTC with logo
- [ ] Filter by "top gainers"
- [ ] All results display logos
- [ ] Toggle between table/card view
- [ ] Logos persist across view changes

### Test 2.6 - Profile / Watchlist
**URL:** `http://localhost:5000/profile` (if logged in)
**Checklist:**
- [ ] Saved coins in watchlist display logos
- [ ] Remove coin and re-add: logo loads again
- [ ] All watchlist functions work with images

---

## Phase 3: Cross-Browser Testing

### Test 3.1 - Firefox
- [ ] All images load correctly
- [ ] Fallback divs display properly
- [ ] No console errors
- [ ] CSP headers accepted

### Test 3.2 - Chrome/Edge
- [ ] All images load correctly
- [ ] Performance is good (images cached)
- [ ] DevTools shows no CSP violations
- [ ] Images from coingecko.com load from cache on reload

### Test 3.3 - Safari
- [ ] Images display properly
- [ ] No rendering issues with fallback divs
- [ ] Console clean

---

## Phase 4: Performance Testing

### Test 4.1 - Image Load Time
**Measurement:**
- Open Network tab in DevTools
- Visit `/coins` page
- Measure time to load all initial images
- Expected: <2 seconds for full page

### Test 4.2 - Cache Effectiveness
**Measurement:**
- Navigate away from `/coins`
- Return to `/coins`
- Check DevTools: images should be from cache (grey in network tab)
- Expected: <500ms reload time

### Test 4.3 - Infinite Scroll Performance
**Action:**
- Scroll to bottom of `/coins`
- Load next page (should trigger /api/coins?page=2)
- New rows should have images
- Verify no memory leaks (scroll continuously for 30 seconds)

---

## Phase 5: Error Handling

### Test 5.1 - Broken Image URLs
**Setup:**
- Add a fake URL to a coin image temporarily
- Load `/coins`
**Expected:**
- Fallback div shows (with coin symbol)
- No console errors
- Page remains functional

### Test 5.2 - Offline Mode
**Action:**
- Open DevTools
- Set Network to "Offline"
- Try to load `/coins`
**Expected:**
- Page loads with cached coins
- Fallback images appear (no network images load)
- Page remains usable

### Test 5.3 - CoinGecko API Timeout
**Action:**
- Temporarily reduce timeout in coingecko.py to 0.1 seconds
- Restart app
- Visit `/coins`
**Expected:**
- Coins still load with fallback images
- No crashes
- Log shows timeout handling

---

## Phase 6: Production Readiness

### Test 6.1 - Security Check
```bash
# Verify no inline styles or scripts in image tags
grep -r "style=" templates/public/ | grep -i img
# Expected: No results or only safe styles

# Check CSP doesn't have 'unsafe-inline' for img-src
curl -i http://localhost:5000/ | grep -i "img-src"
# Expected: No 'unsafe-inline' in img-src
```

### Test 6.2 - Accessibility
**Checklist:**
- [ ] All images have meaningful `alt` attributes
- [ ] Fallback divs have text content (coin symbol)
- [ ] Tab navigation works
- [ ] Screen reader can identify coins

### Test 6.3 - Mobile Responsiveness
**Devices:**
- [ ] iPhone 12 (375px width)
- [ ] iPad (768px width)
- [ ] Android phone (360px width)

**Checklist for each device:**
- [ ] Images scale appropriately
- [ ] No image overflow
- [ ] Fallback symbols display properly
- [ ] Touch interactions work

---

## Regression Testing

### Test 7.1 - Existing Functionality
- [ ] Login/Signup still works
- [ ] Price filtering works
- [ ] Currency toggle (INR/USD) works
- [ ] Sorting works
- [ ] Modal popups display correctly (with images)
- [ ] Charts load and display
- [ ] News section unaffected

### Test 7.2 - Database & Caching
- [ ] Redis cache populates correctly
- [ ] Metadata cache 24-hour refresh works
- [ ] Database queries unaffected
- [ ] Session data intact

---

## Known Limitations & Acceptable Defaults

| Scenario | Expected Behavior |
|----------|-------------------|
| New coin added after 24h cache refresh | Will show until next refresh or manual cache clear |
| Coin without logo in CoinGecko (rare) | Shows `/static/images/default-coin.png` |
| External CDN temporarily down | Shows fallback image (user symbol in circle) |
| Image URL returns 404 or broken | Shows fallback image |
| User on very slow network | May see fallback during loading, then loads real image when ready |

---

## Test Results Summary

| Test | Status | Notes |
|------|--------|-------|
| 1.1 - Debug Endpoint | ⬜ | Run after testing |
| 1.2 - Cache Population | ⬜ | Check logs |
| 1.3 - CSP Headers | ⬜ | Use curl |
| 2.1 - Home Page | ⬜ | Visual inspection |
| 2.2 - Coins Table | ⬜ | Visual inspection |
| 2.3 - Coins Cards | ⬜ | Visual inspection |
| 2.4 - Coin Detail | ⬜ | Visual inspection |
| 2.5 - Search/Filter | ⬜ | Functional test |
| 2.6 - Watchlist | ⬜ | Functional test |
| 3.1 - Firefox | ⬜ | Cross-browser |
| 3.2 - Chrome | ⬜ | Cross-browser |
| 3.3 - Safari | ⬜ | Cross-browser |
| 4.1 - Load Time | ⬜ | Performance |
| 4.2 - Cache Effectiveness | ⬜ | Performance |
| 4.3 - Infinite Scroll | ⬜ | Performance |
| 5.1 - Broken URLs | ⬜ | Error handling |
| 5.2 - Offline Mode | ⬜ | Error handling |
| 5.3 - API Timeout | ⬜ | Error handling |
| 6.1 - Security | ⬜ | Production |
| 6.2 - Accessibility | ⬜ | Production |
| 6.3 - Mobile | ⬜ | Production |
| 7.1 - Regression | ⬜ | Functionality |
| 7.2 - Cache/DB | ⬜ | Backend |

---

## Sign-off

- [ ] All tests passed
- [ ] No new bugs introduced
- [ ] Performance acceptable
- [ ] Ready for production deployment

**Tested By:** _______________  
**Date:** _______________  
**Notes:** _______________
