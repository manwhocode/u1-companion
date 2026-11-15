import { expect, it } from 'vitest'
import { coverCommand } from '@/utils/u1CoverFans'
const cover={power_detected:true,mode:1,desired_chamber_temp:42,critical_chamber_temp:45,inner_fan:{speed:0,delay:0},exhaust_fan:{speed:.6,speed_threshold:.6}}
it('zero keeps dynamic protection',()=>{expect(coverCommand(cover,'exhaust',0)).toBe('SET_PURIFIER_MODE MODE=1 DESIRE_TEMP=42 ALARM_TEMP=45 FAN_SPEED=0 DYNAMIC_FAN_CONTROL=1')})
it('only lid fans without configuration writes',()=>{expect(coverCommand(cover,'inner',0)).toBe('SET_PURIFIER FAN=inner SPEED=0');expect(coverCommand({...cover,mode:0},'exhaust',50)).toBe('SET_PURIFIER FAN=exhaust SPEED=0.5')})
it('rejects unavailable or unsafe modes and input',()=>{for(const p of [{...cover,power_detected:false},{...cover,mode:2},{...cover,desired_chamber_temp:NaN}])expect(()=>coverCommand(p,'exhaust',0)).toThrow();for(const n of [-1,101,NaN,1.5])expect(()=>coverCommand(cover,'inner',n)).toThrow()})
