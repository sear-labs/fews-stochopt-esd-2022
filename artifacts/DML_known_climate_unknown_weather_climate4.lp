\ LP format - for model browsing. Use MPS format to capture full model detail.
\ Signature: 0x5d7bb683528e29db
Maximize
  - 28950.37554608098 alt_water_cap - 1500 alt_elc_cap
   - 1593.535393700787 irrigation_water[26.67]
   - 6564.821023622048 irrigation_water[53.34]
   - 15261.16588582677 irrigation_water[80.01]
   - 10630.37927165354 irrigation_water[106.68] - 0.0936 util_elc[26.67]
   - 0.3856 util_elc[53.34] - 0.8964 util_elc[80.01]
   - 0.6244 util_elc[106.68] + 46800 yield[26.67] + 192800 yield[53.34]
   + 448200 yield[80.01] + 312200 yield[106.68]
Subject To
 water_cap[26.67]: - alt_water_cap + alt_water[26.67] <= 0
 water_cap[53.34]: - alt_water_cap + alt_water[53.34] <= 0
 water_cap[80.01]: - alt_water_cap + alt_water[80.01] <= 0
 water_cap[106.68]: - alt_water_cap + alt_water[106.68] <= 0
 water[26.67]: - water[26.67] + irrigation_water[26.67] + alt_water[26.67]
   >= -26.67
 water[53.34]: - water[53.34] + irrigation_water[53.34] + alt_water[53.34]
   >= -53.34
 water[80.01]: - water[80.01] + irrigation_water[80.01] + alt_water[80.01]
   >= -80.01
 water[106.68]: - water[106.68] + irrigation_water[106.68]
   + alt_water[106.68] >= -106.68
 elc_water[26.67]: 5283.425941929134 irrigation_water[26.67]
   + 33021.41213705709 alt_water[26.67] - elc[26.67] <= 0
 elc_water[53.34]: 5283.425941929134 irrigation_water[53.34]
   + 33021.41213705709 alt_water[53.34] - elc[53.34] <= 0
 elc_water[80.01]: 5283.425941929134 irrigation_water[80.01]
   + 33021.41213705709 alt_water[80.01] - elc[80.01] <= 0
 elc_water[106.68]: 5283.425941929134 irrigation_water[106.68]
   + 33021.41213705709 alt_water[106.68] - elc[106.68] <= 0
 elc_cap[26.67]: - 1944 alt_elc_cap + alt_elc[26.67] <= 0
 elc_cap[53.34]: - 1944 alt_elc_cap + alt_elc[53.34] <= 0
 elc_cap[80.01]: - 1944 alt_elc_cap + alt_elc[80.01] <= 0
 elc_cap[106.68]: - 1944 alt_elc_cap + alt_elc[106.68] <= 0
 elc_balance[26.67]: alt_elc[26.67] + util_elc[26.67] - elc[26.67] >= 0
 elc_balance[53.34]: alt_elc[53.34] + util_elc[53.34] - elc[53.34] >= 0
 elc_balance[80.01]: alt_elc[80.01] + util_elc[80.01] - elc[80.01] >= 0
 elc_balance[106.68]: alt_elc[106.68] + util_elc[106.68] - elc[106.68]
   >= 0
 crop_yield[26.67]: - 0.2014 water[26.67] + yield[26.67] + [
   0.0014 water[26.67] ^2 ] <= -3.747
 crop_yield[53.34]: - 0.2014 water[53.34] + yield[53.34] + [
   0.0014 water[53.34] ^2 ] <= -3.747
 crop_yield[80.01]: - 0.2014 water[80.01] + yield[80.01] + [
   0.0014 water[80.01] ^2 ] <= -3.747
 crop_yield[106.68]: - 0.2014 water[106.68] + yield[106.68] + [
   0.0014 water[106.68] ^2 ] <= -3.747
Bounds
 irrigation_water[26.67] <= 7.62
 irrigation_water[53.34] <= 7.62
 irrigation_water[80.01] <= 7.62
 irrigation_water[106.68] <= 7.62
End
