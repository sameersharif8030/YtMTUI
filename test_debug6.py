import asyncio
from textual.widgets import Input, ListView
from ytmtui.app import YtMTUI
from ytmtui.ytmusic import Track, YTMusicService

async def test():
    app = YtMTUI(volume=0)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        print('App mounted')
        
        library = app.query_one('#library')
        search_results_list = library.query_one('#search-results-list')
        
        library.active_tab = 'search'
        await asyncio.sleep(0.01)
        
        from ytmtui.ytmusic import Track
        fake_tracks = [Track(id=f'test{i}', title=f'Song {i}', artist=f'Artist {i}', album='Album', duration_s=90 + i) for i in range(5)]
        
        library.set_search_results(fake_tracks)
        print('search_results:', len(library.search_results))
        
        # Direct mount test
        library._search_results_list.clear()
        from ytmtui.ui.widgets import _track_item
        items = [_track_item(t, current=False) for t in fake_tracks]
        print('Items to mount:', len(items))
        
        await asyncio.sleep(0.2)
        print('Before mount, children:', len(library._search_results_list.children))
        
        mount_result = library._search_results_list.mount(*items)
        print('Mount result:', mount_result)
        await mount_result
        print('Mount completed')
        print('Children count after mount:', len(search_results_list.children))

asyncio.run(test())