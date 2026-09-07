\ LP format - for model browsing. Use MPS format to capture full model detail.
\ Signature: 0x3c5ecee612596159
Maximize
  - 28950.37554608098 alt_water_cap - 1500 alt_elc_cap
   - 1660.273200787401 irrigation_water[8.89]
   - 8536.991322834645 irrigation_water[26.67]
   - 18795.54566929134 irrigation_water[53.34]
   - 3399.542173228346 irrigation_water[80.01]
   - 1657.549208661417 irrigation_water[106.68] - 0.09752 util_elc[8.89]
   - 0.50144 util_elc[26.67] - 1.104 util_elc[53.34]
   - 0.19968 util_elc[80.01] - 0.09736 util_elc[106.68] + 48760 yield[8.89]
   + 250720 yield[26.67] + 552000 yield[53.34] + 99840 yield[80.01]
   + 48680 yield[106.68]
Subject To
 water_cap[8.89]: - alt_water_cap + alt_water[8.89] <= 0
 water_cap[26.67]: - alt_water_cap + alt_water[26.67] <= 0
 water_cap[53.34]: - alt_water_cap + alt_water[53.34] <= 0
 water_cap[80.01]: - alt_water_cap + alt_water[80.01] <= 0
 water_cap[106.68]: - alt_water_cap + alt_water[106.68] <= 0
 water[8.89]: - water[8.89] + irrigation_water[8.89] + alt_water[8.89]
   >= -8.89
 water[26.67]: - water[26.67] + irrigation_water[26.67] + alt_water[26.67]
   >= -26.67
 water[53.34]: - water[53.34] + irrigation_water[53.34] + alt_water[53.34]
   >= -53.34
 water[80.01]: - water[80.01] + irrigation_water[80.01] + alt_water[80.01]
   >= -80.01
 water[106.68]: - water[106.68] + irrigation_water[106.68]
   + alt_water[106.68] >= -106.68
 elc_water[8.89]: 5283.425941929134 irrigation_water[8.89]
   + 33021.41213705709 alt_water[8.89] - elc[8.89] <= 0
 elc_water[26.67]: 5283.425941929134 irrigation_water[26.67]
   + 33021.41213705709 alt_water[26.67] - elc[26.67] <= 0
 elc_water[53.34]: 5283.425941929134 irrigation_water[53.34]
   + 33021.41213705709 alt_water[53.34] - elc[53.34] <= 0
 elc_water[80.01]: 5283.425941929134 irrigation_water[80.01]
   + 33021.41213705709 alt_water[80.01] - elc[80.01] <= 0
 elc_water[106.68]: 5283.425941929134 irrigation_water[106.68]
   + 33021.41213705709 alt_water[106.68] - elc[106.68] <= 0
 elc_cap[8.89]: - 1944 alt_elc_cap + alt_elc[8.89] <= 0
 elc_cap[26.67]: - 1944 alt_elc_cap + alt_elc[26.67] <= 0
 elc_cap[53.34]: - 1944 alt_elc_cap + alt_elc[53.34] <= 0
 elc_cap[80.01]: - 1944 alt_elc_cap + alt_elc[80.01] <= 0
 elc_cap[106.68]: - 1944 alt_elc_cap + alt_elc[106.68] <= 0
 elc_balance[8.89]: alt_elc[8.89] + util_elc[8.89] - elc[8.89] >= 0
 elc_balance[26.67]: alt_elc[26.67] + util_elc[26.67] - elc[26.67] >= 0
 elc_balance[53.34]: alt_elc[53.34] + util_elc[53.34] - elc[53.34] >= 0
 elc_balance[80.01]: alt_elc[80.01] + util_elc[80.01] - elc[80.01] >= 0
 elc_balance[106.68]: alt_elc[106.68] + util_elc[106.68] - elc[106.68]
   >= 0
 crop_yield[8.89]: - 0.2014 water[8.89] + yield[8.89] + [
   0.0014 water[8.89] ^2 ] <= -3.747
 crop_yield[26.67]: - 0.2014 water[26.67] + yield[26.67] + [
   0.0014 water[26.67] ^2 ] <= -3.747
 crop_yield[53.34]: - 0.2014 water[53.34] + yield[53.34] + [
   0.0014 water[53.34] ^2 ] <= -3.747
 crop_yield[80.01]: - 0.2014 water[80.01] + yield[80.01] + [
   0.0014 water[80.01] ^2 ] <= -3.747
 crop_yield[106.68]: - 0.2014 water[106.68] + yield[106.68] + [
   0.0014 water[106.68] ^2 ] <= -3.747
Bounds
 irrigation_water[8.89] <= 7.62
 irrigation_water[26.67] <= 7.62
 irrigation_water[53.34] <= 7.62
 irrigation_water[80.01] <= 7.62
 irrigation_water[106.68] <= 7.62
End
