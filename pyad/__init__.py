"""An optionally asynchronous multi-threaded downloader module for Python."""
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
import copy

name = "pyad"
__version__ = "1.0.1"

class Downloader:
    """
    An optionally asynchronous multi-threaded downloader class using aiohttp

    Attributes:

        - url (str): The URL to download
        - file (str or path-like object): The filename to write the download to.
        - threads (int): The number of threads to use to download
        - session (aiohttp.ClientSession): An existing session to use with aiohttp
        - new_session (bool): True if a session was not passed, and the downloader created a new one
        - progress_bar (bool): Whether to output a progress bar or not
        - aiohttp_args (dict): Arguments to be passed in each aiohttp request. If you supply a Range header using this, it will be overwritten in fetch()
    """
    def __init__(self, url, file, threads=4, session=None, progress_bar=True, aiohttp_args={"method": "GET"}, create_dir=True):
        """Assigns arguments to self for when asyncstart() or start() calls download.
        
        All arguments are assigned directly to self except for: 

            - session: if not passed, a ClientSession is created
            - aiohttp_args: if the key "method" does not exist, it is set to "GET"
            - create_dir: see parameter description
        
        Parameters:

            - url (str): The URL to download
            - file (str or path-like object): The filename to write the download to.
            - threads (int): The number of threads to use to download
            - session (aiohttp.ClientSession): An existing session to use with aiohttp
            - progress_bar (bool): Whether to output a progress bar or not
            - aiohttp_args (dict): Arguments to be passed in each aiohttp request. If you supply a Range header using this, it will be overwritten in fetch()
            - create_dir (bool): If true, the directories encompassing the file will be created if they do not exist already.
        """
        self.url = url
        if create_dir:
            parent_directory = Path(file).parent
            parent_directory.mkdir(parents=True, exist_ok=True)
        self.file = file
        self.threads = threads
        if not session:
            self.session = aiohttp.ClientSession()
            self.new_session = True
        else:
            self.session = session
            self.new_session = False
        self.progress_bar = progress_bar
        self.aiohttp_args = aiohttp_args

    def start(self, content_length=None):
        """Calls asyncstart() synchronously"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.asyncstart(content_length))

    async def asyncstart(self, content_lenght):
        """Re-initializes file and calls download() with it. Closes session if necessary"""
        await self.download(content_lenght)
        if self.new_session:
            await self.session.close()

    async def fetch(self, progress=False, filerange=(0,"")):
        """Individual thread for fetching files.

        Parameters:

            - progress (bool or tqdm.Progress): the progress bar (or lack thereof) to update
            - filerange (tuple): the range of the file to get
        """
        temp_args = copy.deepcopy(self.aiohttp_args)
        temp_args["method"] = "GET"
        async with aiofiles.open(self.file, "wb") as fileobj:
            if "headers" not in temp_args:
                temp_args["headers"] = dict()
            temp_args["headers"]["Range"] = f"bytes={filerange[0]}-{filerange[1]}"
            async with self.session.request(url=self.url, **temp_args) as filereq:
                offset = filerange[0]
                await fileobj.seek(offset)
                async for chunk in filereq.content.iter_any():
                    if progress:
                        progress.update(len(chunk))
                    await fileobj.write(chunk)

    async def download(self, content_length=None):
        """Generates ranges and calls fetch() with them."""
        temp_args = copy.deepcopy(self.aiohttp_args)
        temp_args["method"] = "HEAD"
        async with self.session.request(url=self.url, **temp_args) as head:
            if content_length:
                length = content_length
            else:
                length = int(head.headers["Content-Length"])
            start = -1
            base = int(length / self.threads)
            ranges = list()
            for counter in range(self.threads - 1):
                ranges.append((start + 1, start + base))
                start += base    
            ranges.append((start + 1, length))
            if self.progress_bar:
                from tqdm import tqdm
                with tqdm(total=length, unit_scale=True, unit="B") as progress:
                    await asyncio.gather(*[self.fetch(progress, filerange) for filerange in ranges])
            else:
                await asyncio.gather(*[self.fetch(False, filerange) for filerange in ranges])