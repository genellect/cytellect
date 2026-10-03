import {describe,expect,it} from "vitest";
import {formatValue} from "./types";

describe("scientific value display",()=>{
 it.each([[1e-8,"1e-8"],[-1e-8,"-1e-8"],[1.234567e-9,"1.2346e-9"],[-0.00000001234567,"-1.2346e-8"]])("keeps nonzero %s visible with its sign",(value,expected)=>{
  expect(formatValue(value)).toBe(expected);
 });
 it("distinguishes true zero from missing and non-finite values",()=>{
  expect(formatValue(0)).toBe("0");
  for(const value of [null,undefined,NaN,Infinity,-Infinity])expect(formatValue(value)).toBe("—");
 });
 it("retains five significant digits for small fractions and usual measurements",()=>{
  expect(formatValue(0.0001234567)).toBe("0.00012346");
  expect(formatValue(1234.567)).toBe("1,234.6");
  expect(formatValue(-24.56789)).toBe("-24.568");
  expect(formatValue(0.0001)).toBe("0.0001");
  expect(formatValue("not recorded")).toBe("not recorded");
 });
});
