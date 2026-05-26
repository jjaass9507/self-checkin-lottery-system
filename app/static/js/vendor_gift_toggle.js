window.addEventListener('load', function () {
    if (typeof window.claimVendorGift !== 'function') return;
    window.claimVendorGift = async function (event, id, name) {
        if (event && event.stopPropagation) event.stopPropagation();
        const person = Array.isArray(window.fullDataCache)
            ? window.fullDataCache.find(p => Number(p.id) === Number(id))
            : null;
        const nextClaimed = !(person && person.vendor_gift_claimed);
        const message = nextClaimed
            ? `確認 [ ${name} ] 已領取公司禮品？`
            : `確認取消 [ ${name} ] 的公司禮品領取紀錄？`;
        if (!confirm(message)) return;
        try {
            const res = await fetch('/checkin/api/toggle_vendor_gift', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, claimed: nextClaimed })
            });
            const data = await res.json();
            if (data.success) {
                if (person) person.vendor_gift_claimed = !!data.vendor_gift_claimed;
                if (typeof window.renderTable === 'function') window.renderTable();
                const lastUpdatedEl = document.getElementById('last-updated');
                if (lastUpdatedEl) lastUpdatedEl.innerText = (data.vendor_gift_claimed ? '已確認禮品: ' : '已取消禮品: ') + name;
            } else {
                alert(data.message || '操作失敗');
            }
        } catch (e) {
            alert('操作失敗');
        }
    };
});
