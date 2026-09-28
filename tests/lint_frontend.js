const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'app', 'static', 'index.html');
const html = fs.readFileSync(filePath, 'utf8');

let errors = [];
let warnings = [];

// 1. Check Document Structure
if (!html.toLowerCase().startsWith('<!doctype html>')) {
    warnings.push('Missing or non-standard <!DOCTYPE html> declaration at start');
}

const requiredTags = ['html', 'head', 'body', 'title'];
requiredTags.forEach(tag => {
    // Word boundary so <head doesn't match <header
    const openCount = (html.match(new RegExp(`<${tag}(\\s+[^>]*)?>`, 'gi')) || []).length;
    const closeCount = (html.match(new RegExp(`</${tag}>`, 'gi')) || []).length;
    if (openCount === 0) {
        errors.push(`Missing opening <${tag}> tag`);
    }
    if (closeCount === 0) {
        errors.push(`Missing closing </${tag}> tag`);
    }
    if (openCount !== closeCount) {
        errors.push(`Mismatched <${tag}> tags: ${openCount} opened vs ${closeCount} closed`);
    } else {
        console.log(`[PASS] Tag <${tag}>: Balanced (${openCount} opened, ${closeCount} closed)`);
    }
});

// 2. Extract and Validate Embedded JavaScript
const scriptRegex = /<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/gi;
let match;
let scriptIndex = 0;
while ((match = scriptRegex.exec(html)) !== null) {
    scriptIndex++;
    const code = match[1];
    try {
        new Function(code);
        console.log(`[PASS] Inline Script #${scriptIndex}: Valid JS Syntax (${code.length} characters)`);
    } catch (err) {
        errors.push(`Inline Script #${scriptIndex} Syntax Error: ${err.message}`);
    }
}

// 3. Extract and Validate Embedded CSS
const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
let styleIndex = 0;
while ((match = styleRegex.exec(html)) !== null) {
    styleIndex++;
    const css = match[1];
    const openBraces = (css.match(/\{/g) || []).length;
    const closeBraces = (css.match(/\}/g) || []).length;
    if (openBraces !== closeBraces) {
        errors.push(`Style block #${styleIndex}: Mismatched braces { (${openBraces}) vs } (${closeBraces})`);
    } else {
        console.log(`[PASS] Style block #${styleIndex}: Braces balanced (${openBraces} rules, ${css.length} characters)`);
    }
}

// 4. Duplicate ID check
const idRegex = /\sid=["']([^"']+)["']/gi;
const seenIds = new Set();
const duplicateIds = new Set();
while ((match = idRegex.exec(html)) !== null) {
    const id = match[1];
    if (seenIds.has(id)) {
        duplicateIds.add(id);
    }
    seenIds.add(id);
}
if (duplicateIds.size > 0) {
    warnings.push(`Duplicate element IDs found: ${Array.from(duplicateIds).join(', ')}`);
} else {
    console.log(`[PASS] Unique Element IDs check: All ${seenIds.size} IDs are unique`);
}

// 5. Check API Endpoints referenced in Frontend
const apiEndpoints = [
    '/auth/signup',
    '/auth/login',
    '/centres',
    '/bookings',
    '/payments'
];
apiEndpoints.forEach(ep => {
    if (html.includes(ep)) {
        console.log(`[PASS] Frontend references API endpoint: ${ep}`);
    } else {
        warnings.push(`Frontend does not seem to reference endpoint: ${ep}`);
    }
});

console.log('\n============================= LINT SUMMARY =============================');
if (warnings.length > 0) {
    console.log(`Warnings (${warnings.length}):`);
    warnings.forEach(w => console.log('  ⚠️  ' + w));
}

if (errors.length > 0) {
    console.log(`Errors (${errors.length}):`);
    errors.forEach(e => console.log('  ❌ ' + e));
    process.exit(1);
} else {
    console.log('✅ ALL FRONTEND LINT CHECKS PASSED (HTML, CSS, JS, Element IDs, Endpoints)');
}
